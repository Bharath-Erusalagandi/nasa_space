"""Trains the two mosquito models on HumBugDB (Kiskin et al. 2021, CC BY 4.0) and tests them on held-out recordings.

  detector  mosquito or not, from every mosquito and background recording in the dataset
  species   the 8 species of the HumBugDB species task (Tanzania, IHI cup recordings)

Both splits are by recording, 75% train and 25% test with seed 42, as in the HumBugDB species notebook; 15% of
the training recordings are held back to pick the best epoch. Nothing from a test recording is seen in training.

In training most windows pass through a random speaker, room and noise (channel.py), because the page is shown
with recordings played from a phone to a laptop microphone. Each model is tested twice on the same held-out
recordings: as recorded, and through one fixed draw of that path per window ("through the air").

A room where the page is shown is full of voices, so the detector also gets read speech (LibriSpeech dev-clean,
Panayotov et al. 2015, CC BY 4.0, in DATA/speech/LibriSpeech/dev-clean, split by speaker) and synthetic steady
voice-range tones as background. Without the speech folder it trains on the tones alone.

Run with PyTorch, librosa and the HumBugDB audio in DATA/audio and its metadata in DATA/meta.csv:
  python models/mosquito/train.py DATA [species|detector|export|all]
species and detector can run at the same time (THREADS=8 each); export then writes the files below.
INIT=<folder> starts a model from the weights saved there (a shorter run then adapts it), LR sets the peak rate.
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
import channel as C  # noqa: E402
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
        x = F.mel_windows(F.load(path), step)
    except Exception:
        return np.zeros((0, F.FRAMES, F.N_MELS), np.float32)
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


def feats(mel):
    return C.to_features(torch.from_numpy(mel)).numpy()


def aired(mel, noise, seed=SEED):
    """The windows through one fixed draw of speaker, room and noise each, for validation and testing."""
    gen = torch.Generator().manual_seed(seed)
    return C.to_features(C.over_the_air(torch.from_numpy(mel), torch.from_numpy(noise), gen, keep=0.0)).numpy()


def detector_split(rows):
    pool = [r for r in rows if r["sound_type"] in ("mosquito", "background")]
    train_names, test_names = set(), set()
    for kind in ("mosquito", "background"):
        tr, te = split([r["name"] for r in pool if r["sound_type"] == kind])
        train_names |= tr
        test_names |= te
    fit_names, val_names = split(train_names, seed=SEED + 1, train=0.85)
    return pool, fit_names, val_names, test_names


def background(rows):
    """Background windows used as room noise: training, validation and test recordings kept apart."""
    pool, fit_names, val_names, test_names = detector_split(rows)
    quiet = [r for r in pool if r["sound_type"] == "background"]
    part = lambda names, step: featurise([r for r in quiet if r["name"] in names], lambda r: 0, step, cap=12)[0]
    return part(fit_names, 10), part(val_names, 15), part(test_names, 15)


def speech(step=10, cap=4):
    """Mel windows of read speech for training, validation and testing, with no speaker in two of them."""
    root = DATA / "speech" / "LibriSpeech" / "dev-clean"
    speakers = sorted(p.name for p in root.iterdir()) if root.exists() else []
    if not speakers:
        return [np.zeros((0, F.FRAMES, F.N_MELS), np.float32)] * 3
    train_names, test_names = split(speakers)
    fit_names, val_names = split(train_names, seed=SEED + 1, train=0.85)

    def part(names):
        jobs = [(str(p), step, cap) for name in sorted(names) for p in sorted((root / name).rglob("*.flac"))]
        with ProcessPoolExecutor() as pool:
            return np.concatenate([x for x in pool.map(extract, jobs, chunksize=8) if len(x)])

    return part(fit_names), part(val_names), part(test_names)


def voice_tones(count, seed):
    """Steady tones with a fundamental of 70 to 260 Hz and some of its harmonics: a hum or a held vowel, below any wingbeat."""
    rng = np.random.RandomState(seed)
    t = np.arange(F.WINDOW_SAMPLES) / F.RATE
    out = []
    for _ in range(count):
        f0 = rng.uniform(70, 260)
        wobble = 1 + rng.uniform(0, 0.03) * np.sin(2 * np.pi * rng.uniform(3, 7) * t + rng.uniform(0, 2 * np.pi))
        phase = 2 * np.pi * np.cumsum(f0 * wobble) / F.RATE
        k = np.arange(1, rng.randint(3, int(3800 / f0) + 1) + 1)
        amp = k ** -rng.uniform(0.3, 2.0) * rng.uniform(0.3, 1.0, len(k))
        tone = (amp[:, None] * np.sin(k[:, None] * phase[None, :] + rng.uniform(0, 2 * np.pi, (len(k), 1)))).sum(0)
        tone = tone / np.abs(tone).max() + rng.uniform(0.003, 0.1) * rng.randn(len(t))
        out.append(F.mel_windows(tone.astype(np.float32), 1)[0])
    return np.stack(out)


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


def train(name, xtr, ytr, xva, yva, classes, epochs, noise, noise_val, width=1):
    model = Net(classes, width)
    if os.environ.get("INIT"):
        model.load_state_dict(torch.load(Path(os.environ["INIT"]) / f"{name}.pt"))
    peak = float(os.environ.get("LR", 2e-3))
    counts = np.bincount(ytr, minlength=classes)
    weights = torch.tensor(len(ytr) / (classes * np.maximum(counts, 1)), dtype=torch.float32)
    loss_fn = nn.CrossEntropyLoss(weight=weights)
    opt = torch.optim.AdamW(model.parameters(), lr=peak, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=peak, total_steps=epochs * ((len(ytr) + 127) // 128))
    xt, yt = torch.from_numpy(xtr), torch.from_numpy(ytr.astype(np.int64))
    bank, gen = torch.from_numpy(noise), torch.Generator().manual_seed(SEED)
    val_recorded, val_aired = feats(xva), aired(xva, noise_val)
    best, best_state = -1.0, None
    for epoch in range(epochs):
        model.train()
        order = torch.randperm(len(yt))
        for i in range(0, len(order), 128):
            b = order[i:i + 128]
            opt.zero_grad()
            loss = loss_fn(model(augment(C.to_features(C.over_the_air(xt[b], bank, gen)))), yt[b])
            loss.backward()
            opt.step()
            sched.step()
        recorded = balanced_accuracy(yva, predict(model, val_recorded).argmax(1), classes)
        air = balanced_accuracy(yva, predict(model, val_aired).argmax(1), classes)
        score = (recorded + air) / 2
        print(f"{name} epoch {epoch + 1}/{epochs} validation balanced accuracy {recorded:.3f} as recorded, {air:.3f} through the air", flush=True)
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
    noise_fit, noise_val, noise_test = background(rows)
    print("species windows", len(ys), len(yv), len(ye), "noise windows", len(noise_fit), len(noise_val), len(noise_test), flush=True)
    width = int(os.environ.get("WIDTH", 1))
    species, species_val = train("species", xs, ys, xv, yv, len(SPECIES), epochs=int(os.environ.get("EPOCHS", 30)),
                                 noise=noise_fit, noise_val=noise_val, width=width)
    species_result_width = width
    pe = predict(species, feats(xe))
    names, rec_probs = by_recording(pe, re)
    rec_true = np.array([label(next(r for r in cup if r["name"] == n)) for n in names])
    rec_pred = rec_probs.argmax(1)
    pa = predict(species, aired(xe, noise_test))
    air_pred = by_recording(pa, re)[1].argmax(1)
    genus = lambda c: LABELS[c].split(".")[0]
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
        "through_the_air": {
            "window_balanced_accuracy": balanced_accuracy(ye, pa.argmax(1), len(SPECIES)),
            "recording_balanced_accuracy": balanced_accuracy(rec_true, air_pred, len(SPECIES)),
            "recording_recall": {LABELS[c]: float(np.mean(air_pred[rec_true == c] == c)) for c in range(len(SPECIES))},
            "recording_genus_accuracy": float(np.mean([genus(p) == genus(t) for p, t in zip(air_pred, rec_true)])),
        },
    }
    print(json.dumps(species_result, indent=1), flush=True)
    tag = os.environ.get("TAG", "")
    torch.save(species.state_dict(), WORK / f"species{tag}.pt")
    (WORK / f"species{tag}.json").write_text(json.dumps(species_result, indent=1))


def run_detector(rows):
    pool, fit_names, val_names, test_names = detector_split(rows)
    label = lambda r: 1 if r["sound_type"] == "mosquito" else 0
    xs, ys, _ = featurise([r for r in pool if r["name"] in fit_names], label, step=10, cap=12)
    xv, yv, _ = featurise([r for r in pool if r["name"] in val_names], label, step=15, cap=12)
    xe, ye, re = featurise([r for r in pool if r["name"] in test_names], label, step=15, cap=12)
    speech_fit, speech_val, speech_test = speech()
    tone_fit, tone_val, tone_test = voice_tones(3000, SEED), voice_tones(500, SEED + 1), voice_tones(1000, SEED + 2)
    xs, ys = np.concatenate([xs, speech_fit, tone_fit]), np.concatenate([ys, np.zeros(len(speech_fit) + len(tone_fit), ys.dtype)])
    xv, yv = np.concatenate([xv, speech_val, tone_val]), np.concatenate([yv, np.zeros(len(speech_val) + len(tone_val), yv.dtype)])
    print("detector windows", len(ys), len(yv), len(ye), "speech windows", len(speech_fit), len(speech_val), len(speech_test), flush=True)
    # the room noise is the dataset's own background windows, from the same part of the split as the sound
    detector, detector_val = train("detector", xs, ys, xv, yv, 2, epochs=int(os.environ.get("EPOCHS", 12)),
                                   noise=xs[ys == 0], noise_val=xv[yv == 0])
    pe = predict(detector, feats(xe))[:, 1]
    pa = predict(detector, aired(xe, xe[ye == 0]))[:, 1]

    def flagged(mel, air):
        if not len(mel):
            return None
        return float(np.mean(predict(detector, aired(mel, xe[ye == 0]) if air else feats(mel))[:, 1] >= 0.5))
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
        "through_the_air": {
            "roc_auc": float(roc_auc_score(ye, pa)),
            "recall": float(np.mean(pa[ye == 1] >= 0.5)),
            "false_alarm_rate": float(np.mean(pa[ye == 0] >= 0.5)),
        },
        # held-out speakers and tones, none of them a mosquito
        "voices": {
            "speech_windows": int(len(speech_test)),
            "speech_flagged": flagged(speech_test, False),
            "speech_flagged_through_the_air": flagged(speech_test, True),
            "tone_windows": int(len(tone_test)),
            "tones_flagged": flagged(tone_test, False),
            "tones_flagged_through_the_air": flagged(tone_test, True),
        },
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
        "source": "Trained on HumBugDB (Kiskin et al. 2021, CC BY 4.0, doi:10.5281/zenodo.4904800), with LibriSpeech dev-clean (Panayotov et al. 2015, CC BY 4.0) as background for the detector, by models/mosquito/train.py",
    }
    out = ROOT / "public" / "models"
    out.mkdir(parents=True, exist_ok=True)
    (out / "mosquito.json").write_text(json.dumps(meta, separators=(",", ":")))
    results = {"seed": SEED, "split": "by recording, 75% train / 25% test", "species": species_result, "detector": detector_result}
    (ROOT / "models" / "mosquito" / "results.json").write_text(json.dumps(results, indent=1))

    # One demo clip per species, from the 30 longest test recordings: the one the model gets right as recorded and through
    # the most of 8 simulated speaker-and-room paths, scored the way the browser scores a recording (a window every 4096
    # samples, at least 3 accepted by the detector, species averaged over them). The longer one wins a tie. If none is
    # right as recorded, the one right through the most paths. The screen and docs say how the clips were picked.
    clips_dir = ROOT / "public" / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    noise_test = background(rows)[2]
    PATHS = 8

    def verdict(x):
        if not len(x):
            return None
        accepted = predict(detector, x)[:, 1] >= 0.5
        if accepted.sum() < min(3, len(x)) or not accepted.any():
            return None
        return LABELS[int(predict(species, x[accepted]).mean(0).argmax())]

    def browser_verdict(signal):
        return verdict(F.windows(signal, 8))

    def right_through_the_air(signal, label):
        mel = F.mel_windows(signal, 8)
        return sum(verdict(aired(mel, noise_test, seed=SEED + path)) == label for path in range(PATHS)) if len(mel) else 0

    import soundfile
    clips = []
    for s, name in enumerate(SPECIES):
        candidates = sorted((r for r in cup if r["name"] in species_test and r["species"] == name), key=lambda r: -float(r["length"]))
        chosen, says, right, best = None, None, False, (-1, -1)
        for row in candidates[:30]:
            signal = F.load(str(DATA / "audio" / f"{row['id']}.wav"))[: F.RATE * 6]
            if len(signal) < F.RATE * 3:
                continue
            signal = signal / max(1e-6, float(np.max(np.abs(signal)))) * 0.9
            said = browser_verdict(signal)
            rank = (int(said == LABELS[s]), right_through_the_air(signal, LABELS[s]))
            if rank > best:
                chosen, says, right, best = (row, signal), said, said == LABELS[s], rank
        row, signal = chosen
        file = f"{LABELS[s].replace('. ', '-').replace(' ', '-').lower()}.wav"
        soundfile.write(str(clips_dir / file), signal, F.RATE, subtype="PCM_16")
        clips.append({"file": f"clips/{file}", "label": LABELS[s], "humbugdb_id": int(row["id"]),
                      "seconds": round(len(signal) / F.RATE, 2), "model_says": says, "picked_because_right": right,
                      "right_through_simulated_paths": f"{best[1]} of {PATHS}"})
    (clips_dir / "clips.json").write_text(json.dumps({
        "source": "HumBugDB (Kiskin et al. 2021), CC BY 4.0, doi:10.5281/zenodo.4904800. Test-set recordings, cut to 6 s and normalised.",
        "picked": "per species, of the 30 longest test recordings, the one the model gets right as recorded and through the most of 8 simulated speaker-and-room paths",
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
