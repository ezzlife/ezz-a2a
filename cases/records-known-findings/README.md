# records known findings

`source/` is an unmodified copy of `records.py` from
[kennethreitz/records](https://github.com/kennethreitz/records) ("SQL for Humans",
first released in 2014) at `f2c5307d76e7909e7b0476e0b004590486ebdf37`, the merge of
2018-02-15 (git blob `c5598af561d5b438b2a45d70b8d80fb103d73732`, SHA-256
`204349b6cf76f8ebcc210805e187ae1317d49260741db9c51db610c72d9cb4d4`), kept under its ISC
license (`source/LICENSE`, Copyright (c) 2016 Kenneth Reitz). `.gitattributes` marks
`source/` as `-text` so a checkout keeps the upstream bytes.

`expected.json` lists five real defects and three plausible-looking false
ones. Each real defect is present in this version and was later fixed or
reported upstream; the `evidence` field names the commit, issue or pull
request. The answer key therefore comes from the project's own history, not
from the reviewer being measured.

Run the review on it:

```powershell
.venv/Scripts/python.exe -m ezz_a2a.review cases/records-known-findings/task.json --repository cases/records-known-findings/source --output evidence/<new-name>.json --model sonnet --enable-claude
```
