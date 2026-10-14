# Menulis aturan

Berkas `rules/*.json` berbentuk `{"schema_version":1,"rules":[...]}`. Validasi: `python -m nsd rules-validate`.

**Kondisi** (semua harus terpenuhi): `id_pemeriksaan:status[|status][kunci=nilai]`, mis.
`smb.unc:fail[category=access_denied]`. Status: `pass|fail|warning|unknown`.

**Keyakinan** dihitung otomatis: kondisi terpenuhi + kode error cocok = *tinggi*; hanya kondisi = *sedang*;
hanya kode (tanpa kondisi) = *rendah* (petunjuk). Kode error **tidak pernah** cukup untuk aturan berbasis bukti.

**Aksi**: hanya operasi di `security/allowlist.py` (`advise`, `start_service`, `enable_specific_firewall_rule`,
`share_printer`, `set_network_profile_private`). Operasi terlarang (disable_firewall, enable_smb1, run_powershell, …) membuat aturan ditolak.

**Konsistensi yang dipaksa skema:** risk `high`/`security_sensitive` ⇒ `auto_policy: blocked`; aksi pengubah ⇒ wajib
`snapshot_keys`, `verification`, `rollback.type`, dan tidak boleh `read_only`.

**Kriteria aturan baru** (vision B.13): reproduksi kegagalan, tes negatif, batasan OS, aksi allowlist, verifikasi,
rollback terdokumentasi, tidak menurunkan keamanan, idempoten.
