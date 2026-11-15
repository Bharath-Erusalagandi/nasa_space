"""What a small speaker, a room and a second microphone do to a recording, applied to mel power windows.

The models are trained on recordings made right next to the mosquito. In a demonstration the recording is played
from a phone and heard by a laptop: the speaker has no bass and an uneven response, the room adds echo, and the
room's own noise is mixed in. over_the_air() draws one such path at random for every window:

  speaker and microphone   second- to fourth-order roll-off below a corner between 200 Hz and 1.5 kHz, a tilt of
                           up to 6 dB per octave either way, and three broad peaks or dips of up to 8 dB
  room                     in half the windows one reflection 0.2 to 3 ms late (a desk or a screen), which combs the
                           spectrum; every frame leaves a tail that decays by 60 dB in 0.1 to 0.8 s; the level
                           wanders by about 1.5 dB from frame to frame, as a hand-held phone does
  noise                    a recorded background window mixed with coloured noise, from 5 dB above the sound to
                           30 dB below it

The effects act on power, so the cross terms between sound, echo and noise are left out.
"""

import librosa
import torch

import features as F

FREQ = torch.tensor(librosa.mel_frequencies(n_mels=F.N_MELS + 2, fmin=0, fmax=F.RATE / 2)[1:-1], dtype=torch.float32)
OCTAVES = torch.log2(FREQ / 1000.0)[None, :]
FRAME_SECONDS = F.HOP / F.RATE


def to_features(mel):
    """(n, FRAMES, N_MELS) mel power to (n, N_MELS, FRAMES) standardised log-mel, the same as features.window_features."""
    db = 10.0 * torch.log10(torch.clamp(mel, min=1e-10))
    db = torch.clamp(db - db.amax(dim=(1, 2), keepdim=True), min=-F.TOP_DB)
    centred = db - db.mean(dim=(1, 2), keepdim=True)
    std = centred.pow(2).mean(dim=(1, 2), keepdim=True).sqrt()
    return (centred / torch.where(std > 1e-6, std, torch.ones_like(std))).transpose(1, 2)


def over_the_air(mel, noise, gen, keep=0.15):
    """mel: (n, FRAMES, N_MELS) power. noise: (m, FRAMES, N_MELS) background windows. A share `keep` is left as recorded."""
    n = len(mel)
    u = lambda lo, hi: lo + (hi - lo) * torch.rand(n, 1, generator=gen)

    corner = 200.0 * 7.5 ** torch.rand(n, 1, generator=gen)
    order = torch.randint(2, 5, (n, 1), generator=gen)
    gain = -10.0 * torch.log10(1.0 + (corner / FREQ[None, :]) ** (2 * order)) + u(-6, 6) * OCTAVES
    for _ in range(3):
        gain = gain + u(-8, 8) * torch.exp(-0.5 * ((OCTAVES - u(-2.5, 2.0)) / u(0.2, 0.8)) ** 2)
    echo = u(0, 0.8) * (torch.rand(n, 1, generator=gen) < 0.5)
    comb = 1.0 + echo ** 2 + 2.0 * echo * torch.cos(2.0 * torch.pi * FREQ[None, :] * u(0.0002, 0.003))
    out = mel * (comb * 10.0 ** (gain / 10.0))[:, None, :]
    out = out * 10.0 ** (0.15 * torch.randn(n, out.shape[1], 1, generator=gen))

    decay = 10.0 ** (-6.0 * FRAME_SECONDS / u(0.1, 0.8))
    wet = u(0, 1)
    tail = torch.zeros_like(out[:, 0])
    frames = []
    for t in range(out.shape[1]):
        frames.append(out[:, t] + wet * tail)
        tail = decay * (tail + out[:, t])
    out = torch.stack(frames, 1)

    recorded = noise[torch.randint(len(noise), (n,), generator=gen)] * (10.0 ** (u(-6, 6) * OCTAVES / 10.0))[:, None, :]
    coloured = (FREQ[None, :] ** -u(0, 2.5))[:, None, :] * torch.exp(0.25 * torch.randn(out.shape, generator=gen))
    total = lambda x: x.sum(dim=(1, 2), keepdim=True).clamp(min=1e-20)
    share = u(0, 1)[:, :, None]
    mixed = share * recorded / total(recorded) + (1 - share) * coloured / total(coloured)
    out = out + mixed * total(out) / 10.0 ** (u(-5, 30)[:, :, None] / 10.0)

    kept = torch.rand(n, 1, 1, generator=gen) < keep
    return torch.where(kept, mel, out)
