import sys
sys.dont_write_bytecode = True

import json
import warnings
from pyparsing.tools.cvt_pyparsing_pep8_names import pep8_converter

source = (
    'expr = pp.locatedExpr(pp.Word("setName")).setResultsName("asList")\n'
    'result = expr.parseString(text, parseAll=True, asList=False)\n'
)

with warnings.catch_warnings(record=True) as captured:
    warnings.simplefilter("always")
    transformed = pep8_converter.transform_string(source)

print(json.dumps({
    "answer": {
        "source": transformed,
        "warnings": [str(w.message) for w in captured],
    }
}))