# Fusionify Audio Intelligence

**Your music. Your visual direction.**

Alat analisis musik dan timing video untuk Claude melalui MCP dan Agent Skills. Fokus awal: JJ, remix, dan konten yang mengikuti musik dari file pengguna.

## Status v0.1

| Kemampuan | Status |
| --- | --- |
| Analisis file MP3/WAV/FLAC/OGG/M4A lokal | Implemented |
| Estimasi tempo, kandidat beat, energi dan kenaikan energi | Implemented; hasil perlu ditinjau |
| Rencana penanda edit sesuai rentang musik | Implemented |
| Render waveform vertikal dengan soundtrack asli | Implemented; template tetap |
| MCP stdio untuk Desktop / Code | Implemented; uji protokol tersedia |
| Plugin dan skill Claude Code | Disediakan; perlu validasi pada aplikasi Claude pengguna |
| Konektor Claude web / remote HTTPS | Planned; belum ada endpoint aktif |
| Editing foto/video bebas dan footage generatif | Planned |
| Pemahaman genre, mood, lirik dan instrumen oleh model audio | Planned |

Skill tidak memproses suara sendiri. Mesin DSP membaca audio lalu memberi Claude data bertimestamp. Estimasi beat tidak menjamin timing benar untuk setiap jenis musik. v0.1 memakai satu estimasi tempo global; musik dengan tempo berubah memerlukan pemeriksaan manual.

## Persiapan

Pasang **Python 3.11+**, **uv**, serta **FFmpeg dan ffprobe** di PATH. Gunakan folder khusus berisi musik yang boleh diproses. Batas awal: 180 detik dan 64 MiB per file.

```bash
git clone https://github.com/FUSIONIFY-ID/Fusionify_Audio_Intelligence.git
cd Fusionify_Audio_Intelligence
uv sync
uv run fusionify-audio doctor
```

Perintah tidak memerlukan API key atau model berbayar untuk DSP/visualizer lokal. Dependency Python tetap perlu diunduh saat pemasangan pertama.

## Uji CLI

macOS/Linux, ganti folder dan nama file sesuai komputer:

```bash
export FAI_MEDIA_ROOT="/absolute/path/to/music"
uv run fusionify-audio analyze "track.mp3"
uv run fusionify-audio plan ANALYSIS_ID
```

PowerShell:

```powershell
$env:FAI_MEDIA_ROOT = 'C:\Users\you\Music'
uv run fusionify-audio analyze 'track.mp3'
```

Analisis disimpan lokal di `~/.fusionify-audio` secara default. Atur `FAI_STATE_ROOT` atau `--state-root` untuk memindahkannya. Setiap analisis menghasilkan ID baru. Render memverifikasi hash sumber agar analisis lama tidak diterapkan ke file yang berubah.

## Claude Code

Untuk mencoba plugin dari checkout, setelah `FAI_MEDIA_ROOT` tersedia di lingkungan proses Claude:

```bash
claude --plugin-dir /absolute/path/to/Fusionify_Audio_Intelligence
```

Atau tambahkan katalog repo dari sesi Claude Code setelah repo terisi:

```text
/plugin marketplace add FUSIONIFY-ID/Fusionify_Audio_Intelligence
/plugin install fusionify-audio-intelligence@fusionify-audio
```

Paket menyertakan konfigurasi MCP yang menjalankan `uv`. Pastikan executable tersebut dapat ditemukan oleh aplikasi Claude. Periksa `/mcp` jika tool tidak muncul. Jalankan `claude plugin validate /absolute/path/to/Fusionify_Audio_Intelligence --strict` dengan CLI Claude yang terpasang untuk validasi manifest yang otoritatif.

## Claude Desktop

Tambahkan entri ini ke konfigurasi MCP Desktop. Ganti semua path, termasuk path executable `uv` bila diperlukan. Jangan menimpa entri server lain.

```json
{
  "mcpServers": {
    "fusionify-audio": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/Fusionify_Audio_Intelligence", "fusionify-audio", "serve"],
      "env": {"FAI_MEDIA_ROOT": "/absolute/path/to/music"}
    }
  }
}
```

Skill pendamping berada di `skills/music-driven-video/`. Konfigurasi MCP Desktop sendiri tidak otomatis memasang skill. Pasang skill melalui mekanisme skill yang tersedia pada klienmu bila ingin workflow pendampingnya.

Contoh permintaan setelah tool terhubung:

> Analisis track.mp3 dari folder musik yang dikonfigurasi. Ambil durasi penuh, buat rencana edit medium, kemudian render visualizer dengan judul Fusionify. Jelaskan bagian yang timing-nya masih perlu dicek.

## Tool MCP

| Tool | Kegunaan |
| --- | --- |
| `analyze_audio` | Ringkasan dan ID analisis dari path file lokal |
| `get_audio_timeline` | Kandidat beat/energi pada rentang waktu, dengan batas hasil |
| `create_edit_plan` | Penanda edit dengan pemetaan waktu sumber ke video |
| `render_visualizer` | Antrean render template waveform 480×854 dengan musik asli |
| `get_job_status` | Status render dan path MP4 lokal setelah selesai |

Satu render aktif per server; riwayat job maksimal 100 per sesi. Restart menghapus status job dari memori; file hasil tetap ada di folder state. Render memakai seluruh sisa musik bila durasi tidak ditentukan. MP4 lokal tidak otomatis menjadi URL download di chat.

## Claude web dan roadmap

Claude web memerlukan remote MCP yang dapat dijangkau melalui internet. Versi ini **belum menyediakan remote MCP**, OAuth, upload pengguna, atau hosted downloads. Jangan memasukkan URL GitHub sebagai URL konektor MCP. Tahap berikutnya: layanan HTTPS terautentikasi, isolasi aset per pengguna, upload, worker render, dan uji lintas klien.

## Tes pengembang

```bash
uv run python -m unittest discover -s tests -v
uv run python tests/mcp_smoke.py
```

Tes memakai audio sintetis; lagu pengguna tidak disertakan dalam repo. Uji sintetis dan protokol tidak menggantikan pemeriksaan sinkronisasi yang didengar manusia.

## Referensi

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Claude Code plugins](https://code.claude.com/docs/en/plugins)
- [Claude remote connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)

Lihat [SPEC.md](SPEC.md) untuk batas versi dan arah pengembangan.
