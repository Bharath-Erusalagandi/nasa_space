"""Trains the two mosquito models on HumBugDB (Kiskin et al. 2021, CC BY 4.0) and tests them on held-out recordings.

  detector  mosquito or not, from every mosquito and background recording in the dataset
  species   the 8 species of the HumBugDB species task (Tanzania, IHI cup recordings)

Both splits are by recording, 75% train and 25% test with seed 42, as in the HumBugDB species notebook; 15% of
the training recordings are held back to pick the best epoch. Nothing from a test recording is seen in training.

Run with PyTorch, librosa and the HumBugDB audio in DATA/audio and its metadata in DATA/meta.csv:
  python models/mosquito/train.py DATA [species|detector|export|all]
species and detector can run at the same time (THREADS=8 each); export then writes the files below.
Writes public/models/mosquito.json (weights), models/mosquito/results.json (test results) and
lib/pod/__fixtures__/mosquito.json (feature and output checks for the browser code).
"""

import base64
import csv
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import confusion_matrix, roc_auc_score

sys.path.insert(0, str(Path(__file__).parent))
import features as F  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(sys.argv[1] if len(sys.argv) > 1 else "humbug")
PART = sys.argv[2] if len(sys.argv) > 2 else "all"
WORK = DATA / "work"
WORK.mkdir(exist_ok=True)
SEED = 42
torch.manual_seed(SEED)
torch.set_num_threads(int(os.environ.get("THREADS", os.cpu_count() or 4)))

SPECIES = ["an arabiensis", "culex pipiens complex", "ae aegypti", "an funestus ss",
           "an squamosus", "an coustani", "ma uniformis", "ma africanus"]
LABELS = ["An. arabiensis", "Cx. pipiens complex", "Ae. aegypti", "An. funestus",
          "An. squamosus", "An. coustani", "Ma. uniformis", "Ma. africanus"]


def split(names, seed=SEED, train=0.75):
    names = sorted(set(names))
    order = np.random.RandomState(seed).permutation(len(names))
    cut = int(len(names) * train)
    return {names[i] for i in order[:cut]}, {names[i] for i in order[cut:]}


def extract(job):
    path, step, cap = job
    try:
        x = F.windows(F.load(path), step)
    except Exception:
        return np.zeros((0, F.N_MELS, F.FRAMES), np.float32)
    if cap and len(x) > cap:
        x = x[np.linspace(0, len(x) - 1, cap).astype(int)]
    return x


def featurise(rows, label_of, step, cap):
    jobs = [(str(DATA / "audio" / f"{r['id']}.wav"), step, cap) for r in rows]
    with ProcessPoolExecutor() as pool:
        parts = list(pool.map(extract, jobs, chunksize=8))
    xs, ys, rec = [], [], []
    for r, x in zip(rows, parts):
        if len(x):
            xs.append(x)
            ys.append(np.full(len(x), label_of(r)))
            rec.append(np.full(len(x), r["name"]))
    return np.concatenate(xs), np.concatenate(ys), np.concatenate(rec)


class Net(nn.Module):
    def __init__(self, classes, width=1):
        super().__init__()
        def block(cin, cout):
            return [nn.Conv2d(cin, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU()]
        c = [16 * width, 32 * width, 64 * width, 64 * width]
        self.body = nn.Sequential(
            *block(1, c[0]), nn.MaxPool2d(2),
            *block(c[0], c[1]), nn.MaxPool2d(2),
            *block(c[1], c[2]), nn.MaxPool2d(2),
            *block(c[2], c[3]),
        )
        self.drop = nn.Dropout(0.3)
        self.head = nn.Linear(c[3], classes)

    def forward(self, x):
        x = self.body(x.unsqueeze(1)).mean(dim=(2, 3))
        return self.head(self.drop(x))


def augment(x):
    x = x.clone()
    for row in x:
        f = np.random.randint(0, 16)
        f0 = np.random.randint(0, F.N_MELS - f)
        row[f0:f0 + f, :] = 0
        t = np.random.randint(0, 6)
        t0 = np.random.randint(0, F.FRAMES - t)
        row[:, t0:t0 + t] = 0
    return x


def balanced_accuracy(y, p, classes):
    recalls = [np.mean(p[y == c] == c) for c in range(classes) if np.any(y == c)]
    return float(np.mean(recalls))


def predict(model, x):
    model.eval()
    with torch.no_grad():
        return torch.cat([torch.softmax(model(torch.from_numpy(x[i:i + 2048])), 1) for i in range(0, len(x), 2048)]).numpy()


def train(name, xtr, ytr, xva, yva, classes, epochs, width=1):
    model = Net(classes, width)
    counts = np.bincount(ytr, minlength=classes)
    weights = torch.tensor(len(ytr) / (classes * np.maximum(counts, 1)), dtype=torch.float32)
    loss_fn = nn.CrossEntropyLoss(weight=weights)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=2e-3, total_steps=epochs * ((len(ytr) + 127) // 128))
    xt, yt = torch.from_numpy(xtr), torch.from_numpy(ytr.astype(np.int64))
    best, best_state = -1.0, None
    for epoch in range(epochs):
        model.train()
        order = torch.randperm(len(yt))
        for i in range(0, len(order), 128):
            b = order[i:i + 128]
            opt.zero_grad()
            loss = loss_fn(model(augment(xt[b])), yt[b])
            loss.backward()
            opt.step()
            sched.step()
        score = balanced_accuracy(yva, predict(model, xva).argmax(1), classes)
        print(f"{name} epoch {epoch + 1}/{epochs} validation balanced accuracy {score:.3f}", flush=True)
        if score > best:
            best, best_state = score, {k: v.clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    return model, best


def by_recording(probs, rec):
    names = sorted(set(rec))
    return names, np.stack([probs[rec == n].mean(0) for n in names])


def export(model):
    """Conv weights with batch norm folded in, as base64 little-endian float32."""
    layers, mods = [], list(model.body)
    i = 0
    while i < len(mods):
        if isinstance(mods[i], nn.Conv2d):
            conv, bn = mods[i], mods[i + 1]
            scale = bn.weight / torch.sqrt(bn.running_var + bn.eps)
            w = conv.weight * scale[:, None, None, None]
            b = bn.bias - bn.running_mean * scale
            layers.append({"type": "conv", "in": conv.in_channels, "out": conv.out_channels, "w": pack(w), "b": pack(b)})
            i += 3
        elif isinstance(mods[i], nn.MaxPool2d):
            layers.append({"type": "pool"})
            i += 1
        else:
            i += 1
    layers.append({"type": "dense", "in": model.head.in_features, "out": model.head.out_features, "w": pack(model.head.weight), "b": pack(model.head.bias)})
    return layers


def pack(t):
    return base64.b64encode(t.detach().numpy().astype("<f4").tobytes()).decode()


def mel_bands():
    bands = []
    for row in F.MEL:
        nz = np.nonzero(row)[0]
        start = int(nz[0]) if len(nz) else 0
        end = int(nz[-1]) + 1 if len(nz) else 0
        bands.append({"start": start, "w": [round(float(v), 9) for v in row[start:end]]})
    return bands


def species_split(rows):
    cup = [r for r in rows if r["country"] == "Tanzania" and r["location_type"] == "cup" and r["species"] in SPECIES]
    train_names, test_names = set(), set()
    for s in SPECIES:
        tr, te = split([r["name"] for r in cup if r["species"] == s])
        train_names |= tr
        test_names |= te
    return cup, train_names, test_names


def run_species(rows):
    cup, train_names, test_names = species_split(rows)
    fit_names, val_names = split(train_names, seed=SEED + 1, train=0.85)
    label = lambda r: SPECIES.index(r["species"])
    xs, ys, _ = featurise([r for r in cup if r["name"] in fit_names], label, step=5, cap=0)
    xv, yv, _ = featurise([r for r in cup if r["name"] in val_names], label, step=15, cap=0)
    xe, ye, re = featurise([r for r in cup if r["name"] in test_names], label, step=15, cap=0)
    print("species windows", len(ys), len(yv), len(ye), flush=True)
    width = int(os.environ.get("WIDTH", 1))
    species, species_val = train("species", xs, ys, xv, yv, len(SPECIES), epochs=int(os.environ.get("EPOCHS", 30)), width=width)
    species_result_width = width
    pe = predict(species, xe)
    names, rec_probs = by_recording(pe, re)
    rec_true = np.array([label(next(r for r in cup if r["name"] == n)) for n in names])
    rec_pred = rec_probs.argmax(1)
    species_result = {
        "classes": LABELS,
        "test_windows": int(len(ye)),
        "test_recordings": int(len(names)),
        "window_balanced_accuracy": balanced_accuracy(ye, pe.argmax(1), len(SPECIES)),
        "recording_balanced_accuracy": balanced_accuracy(rec_true, rec_pred, len(SPECIES)),
        "recording_recall": {LABELS[c]: float(np.mean(rec_pred[rec_true == c] == c)) for c in range(len(SPECIES))},
        "recording_count": {LABELS[c]: int(np.sum(rec_true == c)) for c in range(len(SPECIES))},
        "recording_confusion": confusion_matrix(rec_true, rec_pred, labels=range(len(SPECIES))).tolist(),
        "validation_balanced_accuracy": species_val,
        "width": species_result_width,
    }
    print(json.dumps(species_result, indent=1), flush=True)
    tag = os.environ.get("TAG", "")
    torch.save(species.state_dict(), WORK / f"species{tag}.pt")
    (WORK / f"species{tag}.json").write_text(json.dumps(species_result, indent=1))


def run_detector(rows):
    pool = [r for r in rows if r["sound_type"] in ("mosquito", "background")]
    groups = {}
    for kind in ("mosquito", "background"):
        tr, te = split([r["name"] for r in pool if r["sound_type"] == kind])
        groups[kind] = (tr, te)
    train_names = groups["mosquito"][0] | groups["background"][0]
    test_names = groups["mosquito"][1] | groups["background"][1]
    fit_names, val_names = split(train_names, seed=SEED + 1, train=0.85)
    label = lambda r: 1 if r["sound_type"] == "mosquito" else 0
    xs, ys, _ = featurise([r for r in pool if r["name"] in fit_names], label, step=10, cap=12)
    xv, yv, _ = featurise([r for r in pool if r["name"] in val_names], label, step=15, cap=12)
    xe, ye, re = featurise([r for r in pool if r["name"] in test_names], label, step=15, cap=12)
    print("detector windows", len(ys), len(yv), len(ye), flush=True)
    detector, detector_val = train("detector", xs, ys, xv, yv, 2, epochs=int(os.environ.get("EPOCHS", 12)))
    pe = predict(detector, xe)[:, 1]
    detector_result = {
        "test_windows": int(len(ye)),
        "test_mosquito_windows": int(np.sum(ye == 1)),
        "test_background_windows": int(np.sum(ye == 0)),
        "test_recordings": int(len(set(re))),
        "roc_auc": float(roc_auc_score(ye, pe)),
        "threshold": 0.5,
        "recall": float(np.mean(pe[ye == 1] >= 0.5)),
        "false_alarm_rate": float(np.mean(pe[ye == 0] >= 0.5)),
        "validation_balanced_accuracy": detector_val,
    }
    print(json.dumps(detector_result, indent=1), flush=True)
    torch.save(detector.state_dict(), WORK / "detector.pt")
    (WORK / "detector.json").write_text(json.dumps(detector_result, indent=1))


def run_export(rows):
    cup, _, species_test = species_split(rows)
    # of the species models trained, the one with the best validation score (the test set does not choose)
    runs = [json.loads(p.read_text()) | {"tag": p.stem[len("species"):]} for p in sorted(WORK.glob("species*.json"))]
    species_result = max(runs, key=lambda r: r["validation_balanced_accuracy"])
    tag = species_result.pop("tag")
    print("species model chosen:", tag or "(base)", "validation", species_result["validation_balanced_accuracy"], flush=True)
    species, detector = Net(len(SPECIES), species_result.get("width", 1)), Net(2)
    species.load_state_dict(torch.load(WORK / f"species{tag}.pt"))
    detector.load_state_dict(torch.load(WORK / "detector.pt"))
    detector_result = json.loads((WORK / "detector.json").read_text())
    meta = {
        "rate": F.RATE, "n_fft": F.N_FFT, "hop": F.HOP, "n_mels": F.N_MELS, "frames": F.FRAMES, "top_db": F.TOP_DB,
        "mel": mel_bands(),
        "detector": {"classes": ["background", "mosquito"], "layers": export(detector)},
        "species": {"classes": LABELS, "layers": export(species)},
        "source": "Trained on HumBugDB (Kiskin et al. 2021, CC BY 4.0, doi:10.5281/zenodo.4904800) by models/mosquito/train.py",
    }
    out = ROOT / "public" / "models"
    out.mkdir(parents=True, exist_ok=True)
    (out / "mosquito.json").write_text(json.dumps(meta, separators=(",", ":")))
    results = {"seed": SEED, "split": "by recording, 75% train / 25% test", "species": species_result, "detector": detector_result}
    (ROOT / "models" / "mosquito" / "results.json").write_text(json.dumps(results, indent=1))

    # One demo clip per species, from the test recordings: the longest one the model gets right when scored the way the
    # browser scores a recording (a window every 4096 samples, at least 3 accepted by the detector, species averaged over
    # them). If none is right, the longest one. The screen and docs say how the clips were picked.
    clips_dir = ROOT / "public" / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    def browser_verdict(signal):
        x = F.windows(signal, 8)
        if not len(x):
            return None
        accepted = predict(detector, x)[:, 1] >= 0.5
        if accepted.sum() < min(3, len(x)) or not accepted.any():
            return None
        return LABELS[int(predict(species, x[accepted]).mean(0).argmax())]

    import soundfile
    clips = []
    for s, name in enumerate(SPECIES):
        candidates = sorted((r for r in cup if r["name"] in species_test and r["species"] == name), key=lambda r: -float(r["length"]))
        chosen, says, right = None, None, False
        for row in candidates:
            signal = F.load(str(DATA / "audio" / f"{row['id']}.wav"))[: F.RATE * 6]
            if len(signal) < F.RATE * 3:
                continue
            signal = signal / max(1e-6, float(np.max(np.abs(signal)))) * 0.9
            verdict = browser_verdict(signal)
            if chosen is None:
                chosen, says = (row, signal), verdict
            if verdict == LABELS[s]:
                chosen, says, right = (row, signal), verdict, True
                break
        row, signal = chosen
        file = f"{LABELS[s].replace('. ', '-').replace(' ', '-').lower()}.wav"
        soundfile.write(str(clips_dir / file), signal, F.RATE, subtype="PCM_16")
        clips.append({"file": f"clips/{file}", "label": LABELS[s], "humbugdb_id": int(row["id"]),
                      "seconds": round(len(signal) / F.RATE, 2), "model_says": says, "picked_because_right": right})
    (clips_dir / "clips.json").write_text(json.dumps({
        "source": "HumBugDB (Kiskin et al. 2021), CC BY 4.0, doi:10.5281/zenodo.4904800. Test-set recordings, cut to 6 s and normalised.",
        "picked": "per species, the longest test recording the model gets right; the longest one if none is right",
        "clips": clips,
    }, indent=1))
    print(json.dumps(clips, indent=1), flush=True)

    # the malaria-relevant question is the genus, so the same test is also scored by group
    groups = [0 if l.startswith("An.") else 1 if l.startswith("Cx.") else 2 if l.startswith("Ae.") else 3 for l in LABELS]
    conf = np.array(species_result["recording_confusion"])
    by_group = np.zeros((4, 4), int)
    for i in range(len(LABELS)):
        for j in range(len(LABELS)):
            by_group[groups[i], groups[j]] += conf[i, j]
    names = ["Anopheles", "Culex", "Aedes", "Mansonia"]
    results["species_group"] = {
        "recall": {names[g]: float(by_group[g, g] / by_group[g].sum()) for g in range(4)},
        "count": {names[g]: int(by_group[g].sum()) for g in range(4)},
        "balanced_accuracy": float(np.mean([by_group[g, g] / by_group[g].sum() for g in range(4)])),
    }
    # malaria mosquito or not: Anopheles against the other three genera
    others = by_group[1:].sum()
    results["malaria_vector"] = {
        "recall": float(by_group[0, 0] / by_group[0].sum()),
        "specificity": float(1 - by_group[1:, 0].sum() / others),
        "anopheles_recordings": int(by_group[0].sum()),
        "other_recordings": int(others),
    }
    (ROOT / "models" / "mosquito" / "results.json").write_text(json.dumps(results, indent=1))

    # checks for the browser code: raw audio in, features and both outputs out
    fixtures = []
    for s in (0, 2):
        row = next(r for r in cup if r["name"] in species_test and label_species(r) == s)
        signal = F.load(str(DATA / "audio" / f"{row['id']}.wav"))[: F.WINDOW_SAMPLES]
        x = F.windows(signal, 1)[:1]
        fixtures.append({
            "label": LABELS[s],
            "signal": [round(float(v), 7) for v in signal],
            "features_head": [round(float(v), 5) for v in x[0, :4, :4].ravel()],
            "detector": [round(float(v), 6) for v in predict(detector, x)[0]],
            "species": [round(float(v), 6) for v in predict(species, x)[0]],
        })
    fx = ROOT / "lib" / "pod" / "__fixtures__"
    fx.mkdir(parents=True, exist_ok=True)
    (fx / "mosquito.json").write_text(json.dumps(fixtures, separators=(",", ":")))
    print("wrote", out / "mosquito.json", (out / "mosquito.json").stat().st_size, "bytes", flush=True)


def label_species(r):
    return SPECIES.index(r["species"]) if r["species"] in SPECIES else -1


def main():
    rows = list(csv.DictReader(open(DATA / "meta.csv")))
    if PART in ("species", "all"):
        run_species(rows)
    if PART in ("detector", "all"):
        run_detector(rows)
    if PART in ("export", "all"):
        run_export(rows)


if __name__ == "__main__":
    main()
