---
doc_id: id_human_escalation
doc_type: escalation_policy
title: Panduan Eskalasi ke Agen Manusia (Sintetis)
version: "1.0"
is_synthetic: true
market: ID
language: id
---

> **DATA PENILAIAN SINTETIS.** Dokumen ini dibuat untuk Darwix AI Engineer Assessment.

# Panduan Eskalasi

## Skenario Eskalasi

- Nasabah meminta "ingin berbicara dengan agen" atau "mau live agent".
- Permintaan penanganan kasus khusus: dispute pembayaran, klaim fraud, negosiasi DP/tenor di luar kebijakan standar.
- Permintaan informasi sensitif yang butuh verifikasi identitas lebih lanjut.

## Proses Eskalasi

1. Verifikasi identitas dasar (tanpa meminta PII berlebih di chat): nama, tanggal lahir, 4 digit terakhir nomor kontrak jika diperlukan.
2. Catat ringkasan kasus dan langkah-langkah yang sudah diambil.
3. Sediakan pilihan waktu kontak dan transfer ke queue agen manusia.

## Bahasa & Dialek

- Bersikap sopan dan gunakan Bahasa Indonesia formal untuk eskalasi; bila nasabah menggunakan bahasa daerah atau campuran (mis. campuran Melayu/Betawi), catat preferensi bahasa untuk agen.

## Batasan Bot

- Bot tidak boleh meminta PII sensitif seperti nomor kartu kredit penuh atau PIN lewat chat.
- Bila topik di luar cakupan (mis. nasabah menanyakan nasabah lain, menanyakan hasil pemeriksaan kredit orang lain), arahkan ke agen manusia.
