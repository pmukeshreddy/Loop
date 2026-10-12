"""Monitoring-only correctness; no training rewards."""
import ast
from decimal import Decimal, InvalidOperation


def _set_f1(left, right):
    left, right = set(left), set(right)
    return 2*len(left & right)/(len(left)+len(right)) if left or right else 1.


def score_deepswe(prediction, answer, answer_type):
    """DeepSWE task answers. Patches need executable verification, so they are unknown (None)."""
    from rlm_opsd.tasks.verify import matches, normalize, parse_answer
    if answer_type == 'patch':
        return None
    fmt = 'set' if answer_type in ('test_ids', 'symbols') else (
        'ordered_list' if isinstance(answer, list) else 'object' if isinstance(answer, dict) else 'scalar')
    try:
        predicted = normalize(parse_answer(str(prediction), fmt), answer_type, fmt)
    except (ValueError, TypeError, AttributeError):
        return 0.
    expected = normalize(answer, answer_type, fmt)
    if answer_type in ('test_ids', 'symbols'):
        return _set_f1(predicted, expected)
    return float(matches(predicted, expected))


def score_answer(prediction, answer, answer_type):
    if answer_type in ('patch', 'test_ids', 'symbols', 'value'):
        return score_deepswe(prediction, answer, answer_type)
    if answer_type not in ('exact','multiple_choice','numeric','list_f1'):
        raise ValueError('unsupported answer_type')
    if answer_type in ('exact','multiple_choice'):
        return float(str(prediction).strip()==str(answer).strip())
    if answer_type=='numeric':
        try:
            left,right=Decimal(str(prediction).strip()),Decimal(str(answer).strip())
            return float(left.is_finite() and right.is_finite() and left==right)
        except InvalidOperation:return 0.
    try:
        left=ast.literal_eval(prediction) if isinstance(prediction,str) else prediction
        right=ast.literal_eval(answer) if isinstance(answer,str) else answer
        if not isinstance(left,list) or not isinstance(right,list):return 0.
        # Set F1 on stripped item representations; ordering/duplicates do not matter.
        left={str(x).strip() for x in left};right={str(x).strip() for x in right}
        return 2*len(left & right)/(len(left)+len(right)) if left or right else 1.
    except (ValueError,SyntaxError,TypeError):return 0.


def score_trajectory(trajectory, answer, answer_type):
    final=trajectory.get('final',{})
    if final.get('type') not in ('FINAL','FINAL_VAR') or final.get('error'):
        return None if answer_type == 'patch' else 0.
    return score_answer(final.get('value',''),answer,answer_type)


def task_success(score):
    """Tracked success; None when correctness needs executable verification."""
    return None if score is None else score == 1.
