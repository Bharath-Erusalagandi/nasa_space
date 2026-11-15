NON_MOSQUITO = {"noise", "non-mosquito", "not mosquito", "no mosquito", "none", "background"}
NO_ANSWER = "(no answer)"


def confusion(true, predicted):
    if len(true) != len(predicted):
        raise ValueError("true and predicted need the same length")
    labels = sorted(set(true) | set(predicted))
    index = {label: i for i, label in enumerate(labels)}
    matrix = [[0] * len(labels) for _ in labels]
    for t, p in zip(true, predicted):
        matrix[index[t]][index[p]] += 1
    recall = {}
    for label in sorted(set(true)):
        row = matrix[index[label]]
        recall[label] = row[index[label]] / sum(row)
    correct = sum(t == p for t, p in zip(true, predicted))
    return {
        "labels": labels,
        "matrix": matrix,
        "recall": recall,
        "accuracy": correct / len(true) if true else None,
    }


def is_mosquito(label):
    return label != NO_ANSWER and label.lower() not in NON_MOSQUITO


def false_alarms(true, predicted):
    clips = [p for t, p in zip(true, predicted) if not is_mosquito(t)]
    return sum(is_mosquito(p) for p in clips), len(clips)


def accuracy_by_distance(true, predicted, distances):
    groups = {}
    for t, p, d in zip(true, predicted, distances):
        correct, n = groups.get(d, (0, 0))
        groups[d] = (correct + (t == p), n + 1)
    return [(d, *groups[d]) for d in sorted(groups)]
