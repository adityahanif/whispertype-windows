# 🎙 WhisperType — Speech to Text untuk Windows

Aplikasi speech-to-text yang mengirim hasil transkripsi langsung ke Notepad, 
Microsoft Word, atau aplikasi apapun yang sedang aktif.

---

## ⚡ Cara Cepat Mulai

1. **Install Python** (jika belum): https://python.org/downloads  
   ✅ Centang "Add Python to PATH"

2. **Jalankan setup** (sekali saja):
   ```
   klik dua kali: setup.bat
   ```

3. **Jalankan aplikasi**:
   ```
   klik dua kali: run.bat
   ```

---

## 🎛 Pengaturan

| Setting | Keterangan |
|---|---|
| **Sumber Audio** | Pilih microphone untuk suara bicara, atau device Loopback untuk audio internal laptop |
| **Model Whisper** | `base` untuk laptop biasa, `small`/`medium` untuk akurasi lebih baik |
| **Bahasa** | Pilih "Indonesia" agar lebih akurat, atau "Auto-detect" |
| **Mode Output** | Clipboard (paste via Ctrl+V) atau Auto-type |
| **Output Delay** | Waktu tunggu sebelum teks dikirim — beri waktu untuk fokus ke Notepad/Word |

---

## 🖥 Cara Pakai (alur normal)

1. Buka Notepad atau Microsoft Word
2. Klik di area ketik di Notepad/Word agar fokus ada di sana
3. Kembali ke WhisperType, klik **▶ Mulai Rekam**
4. Bicara — hasil transkripsi akan langsung muncul di Notepad/Word
5. Klik **⏹ Stop Rekam** jika selesai

> **Tip**: Gunakan Output Delay 0.5–1 detik agar ada waktu untuk berpindah fokus ke Notepad/Word sebelum teks dikirim.

---

## 🔊 Capture Audio Internal (Loopback)

Untuk merekam suara dari YouTube, Zoom, Teams, dll:

1. Di Windows 10/11, aktifkan **Stereo Mix**:
   - Klik kanan ikon speaker di taskbar → Sound Settings
   - Recording → klik kanan area kosong → Show Disabled Devices
   - Klik kanan "Stereo Mix" → Enable
   - Device ini akan muncul di daftar "Sumber Audio"

2. Alternatif: Install **VB-Audio Virtual Cable** (gratis):
   - https://vb-audio.com/Cable/
   - Set sebagai output audio, lalu pilih di daftar Sumber Audio

---

## ❓ Troubleshooting

**Model lama dimuat terus?**  
Model di-cache otomatis setelah download pertama. Tidak perlu download ulang.

**Teks tidak muncul di Word/Notepad?**  
Pastikan jendela Word/Notepad aktif dan kursor berada di area teks sebelum menekan Mulai Rekam. Tambah Output Delay jika perlu.

**Error `No module named 'sounddevice'`?**  
Jalankan ulang `setup.bat` atau: `pip install sounddevice`

**Akurasi kurang baik?**  
Ganti model ke `small` atau `medium`. Pilih bahasa spesifik alih-alih Auto-detect.
