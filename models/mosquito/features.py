"""Log-mel windows for the mosquito models. lib/pod/mosquitoModel.ts computes the same thing in the browser.

One window is 30 STFT frames at 8 kHz (2048-point FFT, hop 512, periodic Hann, no centring), about 2.1 s of audio.
Each window is turned into decibels against its own loudest bin (80 dB floor) and then standardised by its own
mean and standard deviation, so a window can be scored on its own while audio streams in.
"""

import numpy as np
import librosa

RATE = 8000
N_FFT = 2048
HOP = 512
N_MELS = 128
FRAMES = 30
WINDOW_SAMPLES = N_FFT + (FRAMES - 1) * HOP
TOP_DB = 80.0

HANN = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(N_FFT) / N_FFT)).astype(np.float32)
MEL = librosa.filters.mel(sr=RATE, n_fft=N_FFT, n_mels=N_MELS).astype(np.float32)


def power_frames(signal):
    """Power spectrum of every full frame, shape (frames, N_FFT // 2 + 1)."""
    if len(signal) < N_FFT:
        return np.zeros((0, N_FFT // 2 + 1), np.float32)
    count = 1 + (len(signal) - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(count)[:, None]
    spectrum = np.fft.rfft(signal[idx] * HANN, axis=1)
    return (spectrum.real ** 2 + spectrum.imag ** 2).astype(np.float32)


def window_features(mel_frames):
    """mel_frames: (FRAMES, N_MELS) mel power. Returns (N_MELS, FRAMES) standardised log-mel."""
    db = 10.0 * np.log10(np.maximum(mel_frames, 1e-10))
    db = np.maximum(db - db.max(), -TOP_DB)
    std = db.std()
    return ((db - db.mean()) / (std if std > 1e-6 else 1.0)).T.astype(np.float32)


def windows(signal, step):
    """Every window of FRAMES frames, `step` frames apart, shape (n, N_MELS, FRAMES)."""
    mel = power_frames(signal) @ MEL.T
    starts = range(0, len(mel) - FRAMES + 1, step)
    return np.stack([window_features(mel[s:s + FRAMES]) for s in starts]) if len(mel) >= FRAMES else np.zeros((0, N_MELS, FRAMES), np.float32)


def load(path):
    signal, _ = librosa.load(path, sr=RATE, mono=True)
    return signal.astype(np.float32)
