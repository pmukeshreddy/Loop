"""Prefix replacement only; deliberately has no tokenizer or text dependency."""


def _ids(values):
    result = tuple(values)
    if any(type(value) is not int or value < 0 for value in result):
        raise ValueError('token IDs must be nonnegative integers')
    return result


def build_teacher_sequence(student_ids, *, student_prefix, teacher_prefix):
    student, source, target = map(_ids, (student_ids, student_prefix, teacher_prefix))
    if not source or not target:
        raise ValueError('prefixes must not be empty')
    if student[:len(source)] != source:
        raise ValueError('student sequence does not start with the recorded student prefix')
    suffix = student[len(source):]
    teacher = target + suffix
    assert teacher[len(target):] == student[len(source):], 'teacher/student suffix IDs differ'
    return teacher
