"""NF4 base storage with BF16 compute and ordinary FSDP2 parameters."""
import torch
from torch import nn


class NF4Linear(nn.Linear):
    """Keep packed bytes shardable and quantization state in checkpointed buffers.

    Linear4bit's forward replaces FSDP's gathered parameter with Params4bit.
    Use the same bitsandbytes matmul directly, without rebinding the parameter.
    BF16 is only the packed storage container; it must never be dtype-cast.
    """

    def __init__(self, layer):
        nn.Module.__init__(self)
        state = layer.weight.quant_state
        if (state.quant_type != 'nf4' or not state.nested or state.dtype != torch.bfloat16
                or layer.weight.dtype != torch.bfloat16):
            raise ValueError('OPSD requires double-quantized NF4 with BF16 storage/compute')
        self.in_features, self.out_features = layer.in_features, layer.out_features
        self.weight = nn.Parameter(layer.weight.data, requires_grad=False)
        self.bias = layer.bias
        if self.bias is not None:
            self.bias.requires_grad_(False)
        self.blocksize, self.nested_blocksize = state.blocksize, state.state2.blocksize
        for name, tensor in (('absmax', state.absmax), ('code', state.code),
                ('offset', state.offset), ('nested_absmax', state.state2.absmax),
                ('nested_code', state.state2.code)):
            self.register_buffer(name, tensor)

    @property
    def quant_state(self):
        from bitsandbytes.functional import QuantState
        nested = QuantState(absmax=self.nested_absmax, code=self.nested_code,
                            blocksize=self.nested_blocksize, dtype=torch.float32)
        return QuantState(absmax=self.absmax, code=self.code, offset=self.offset,
            shape=torch.Size((self.out_features, self.in_features)), blocksize=self.blocksize,
            quant_type='nf4', dtype=torch.bfloat16, state2=nested)

    def forward(self, x):
        from bitsandbytes import matmul_4bit
        bias = self.bias.to(torch.bfloat16) if self.bias is not None else None
        return matmul_4bit(x.to(torch.bfloat16), self.weight.t(), bias=bias,
                          quant_state=self.quant_state)


def load_nf4_weights(skeleton, config, device):
    """Stream HF weights into NF4 before LoRA, activation checkpointing and FSDP.

    Embeddings, norms and the chunked JSD output head stay frozen in BF16.
    Resume also loads the base to establish quantization metadata before the
    native checkpoint restores model, optimizer and scheduler state.
    """
    from bitsandbytes.nn import Linear4bit
    from transformers import BitsAndBytesConfig
    model = type(skeleton).from_pretrained(config.name, config=skeleton.config,
        trust_remote_code=config.trust_remote_code, dtype=torch.bfloat16,
        device_map={'': str(device)}, quantization_config=BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_quant_storage=torch.bfloat16,
            llm_int8_skip_modules=['lm_head']))
    for name, module in list(model.named_modules()):
        if isinstance(module, Linear4bit):
            parent, _, child = name.rpartition('.')
            setattr(model.get_submodule(parent), child, NF4Linear(module))
    model.requires_grad_(False)
    return model
