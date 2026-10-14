# Arsitektur (implementasi Fase 1)

```
UI (PySide6) / CLI ─► ScanService ─► diagnostics.runner (20 pemeriksaan bertingkat)
                          │                 └─► WindowsAdapter (operasi baca-saja bertipe) / NetProbe (socket)
                          ├─► rules.loader/schema ─► rules.matcher ─► policy_service (gerbang)
                          └─► storage (SQLite: cases, checks, repair_plans, audit) ─► report_service (disamarkan)
```
Rincian rancangan lengkap: `vision.md` Bagian B. Perbedaan dari rancangan: `repairs/` dan `windows/{services,firewall,registry,shares,print_api}.py`
belum dibuat (Fase 2+); `security/audit.py` digantikan `AuditRepository`.
