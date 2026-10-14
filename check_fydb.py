"""Sanity check for a Bluecoins file written by the web app (run before trusting a new version of the write code).
Usage: python check_fydb.py bluecoins.fydb [tracker_file]
Exits 1 and lists the problems if anything Bluecoins relies on is broken."""
import json, sqlite3, sys

db = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro&immutable=1", uri=True)
bad = []
check = lambda ok, msg: ok or bad.append(msg)

check(db.execute("pragma integrity_check").fetchone()[0] == "ok", "SQLite integrity check failed")

# A transfer is two rows that point at each other: sender (ref 1, negative) and receiver (ref 2), same main-currency amount.
rows = {r[0]: r for r in db.execute("""select transactionsTableID, uidPairID, accountReference, amount, deletedTransaction, accountID, accountPairID
  from TRANSACTIONSTABLE where transactionTypeID = 5 and reminderTransaction is null""")}
for id_, uid, ref, amt, deleted, acc, pair in rows.values():
    o = rows.get(uid)
    if not o: bad.append(f"transfer {id_}: its other half {uid} is missing"); continue
    check(o[1] == id_, f"transfer {id_}: other half {uid} points to {o[1]}, not back")
    check({ref, o[2]} == {1, 2}, f"transfer {id_}: sides are {ref} and {o[2]}, expected 1 and 2")
    check(amt == -o[3], f"transfer {id_}: amounts {amt} and {o[3]} don't mirror")
    check(deleted == o[4], f"transfer {id_}: only one half is deleted")
    check(acc == o[6] and pair == o[5], f"transfer {id_}: account links don't cross")

orphans = db.execute("select count(*) from TRANSACTIONSTABLE where itemID not in (select itemTableID from ITEMTABLE)").fetchone()[0]
check(orphans == 0, f"{orphans} transactions point to a missing payee (ITEMTABLE)")

if len(sys.argv) > 2:  # tracker_file must describe this exact database, or the phone may ignore or misread the sync
    t = {k: v for d in json.load(open(sys.argv[2], encoding="utf-8")) for k, v in d.items()}
    setting7 = db.execute("select defaultSettings from SETTINGSTABLE where settingsTableID = 7").fetchone()[0]
    txn = db.execute("select count(*) from TRANSACTIONSTABLE where reminderTransaction is null and transactionTypeID <> 1").fetchone()[0]
    check(t.get("tracking_id") == setting7, f"tracker tracking_id {t.get('tracking_id')} != database setting 7 {setting7}")
    check(t.get("txn") == str(txn), f"tracker txn {t.get('txn')} != {txn} transactions in the database")

print("\n".join(bad) if bad else f"OK: {len(rows)} transfer rows, payees and tracker consistent")
sys.exit(1 if bad else 0)
