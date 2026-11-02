"""UI fixtures preserve existing work and never deliver messages."""

import csv
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import channel
from sandbox import charts, files, inbox, pending, reports, seed
from scripts.prepare_ui_demo import CASES, DATA, install, write_bundle
from tests.support import ScratchTest


class UIDemoTest(ScratchTest):
    def test_committed_bundle_matches_documented_fixtures(self):
        with ZipFile(DATA / "ui-test-data.zip") as archive:
            for name in [case[0] for case in CASES] + ["README.md", "expected_results.csv"]:
                self.assertEqual(archive.read(name).decode("utf-8-sig").replace("\r\n", "\n"),
                                 (DATA / name).read_text(encoding="utf-8-sig"), name)

    def test_contact_override_and_matching_download_preserve_sent_history(self):
        with channel.seeding():
            seed.seed(None)
        rid = "REQ-SYN-thread-2001"
        sent, _ = pending.add("report_email", rid, "SYN-thread-2001", "old@example.com",
                              "History", "Original", key="old", stamp="manual")
        pending.mark_sent(sent["id"])
        rows = install({"SYN-DIST-001": ("Demo reviewer", "reviewer@example.net")})
        self.assertEqual(inbox.get(rid)["contact_email"], "reviewer@example.net")
        self.assertEqual(pending.get(sent["id"])["recipient"], "old@example.com")
        self.assertEqual(rows[0]["recipient"], "reviewer@example.net")
        self.assertEqual(rows[1]["recipient"], "contact@brightline.example")
        with TemporaryDirectory() as folder:
            output = Path(folder)
            bundle = write_bundle(rows, output)
            with ZipFile(bundle) as archive:
                self.assertEqual(archive.read("expected_results.csv"),
                                 (output / "expected_results.csv").read_bytes())
                for filename, *_ in CASES:
                    self.assertEqual(archive.read(filename), (DATA / filename).read_bytes())

    def test_documented_csv_totals_match_fixture_rows(self):
        for filename, _, _, expected, _ in CASES:
            if expected is None:
                continue
            with (DATA / filename).open(encoding="utf-8", newline="") as stream:
                rows = csv.DictReader(stream, delimiter=";" if "semicolon" in filename else ",")
                columns = [c for c in rows.fieldnames if c in ("units_sold", "Menge") or c.endswith("_units")]
                total = sum((Decimal(row[col].replace(",", ".")) for row in rows for col in columns), Decimal(0))
            self.assertEqual(total, expected, filename)

    def test_install_preserves_history_and_is_repeatable(self):
        with channel.seeding():
            seed.seed(None)
        rid = "REQ-SYN-thread-2001"
        sent, _ = pending.add("report_email", rid, "SYN-thread-2001", "old@example.com",
                              "History", "Original body", key="history", stamp="manual")
        pending.mark_sent(sent["id"])
        rows = install()
        self.assertEqual(len(rows), 9)
        self.assertEqual(inbox.get(rid)["contact_email"], "contact@acme.example")
        self.assertEqual(pending.get(sent["id"])["recipient"], "old@example.com")
        self.assertEqual(reports.latest(rid)["stamp"], "ui-demo-preview")
        self.assertEqual(len(charts.for_request("REQ-SYN-thread-2002")), 2)
        for row in rows:
            self.assertIsNone(reports.latest(row["request_id"]))
            self.assertIn("sku" if row["file"].startswith("01") else "\n",
                          files.read_upload(row["request_id"], row["file"]))
        counts = (len(inbox.all_requests()), len(pending.all_pending()),
                  len(channel.messages("SYN-thread-2001")))
        inbox.set_status(rows[0]["request_id"], "done")
        install()
        self.assertEqual(inbox.get(rows[0]["request_id"])["status"], "done")
        self.assertEqual(counts, (len(inbox.all_requests()), len(pending.all_pending()),
                                  len(channel.messages("SYN-thread-2001"))))
        zero = next(r for r in rows if r["period"] == "2026Q4")
        self.assertEqual(zero["database_revenue"], 0)
