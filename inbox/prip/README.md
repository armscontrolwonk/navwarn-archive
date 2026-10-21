# Russian PRIP coastal warnings go here

Paste one or more PRIP texts, in the original Cyrillic, into a UTF-8 .txt file in this folder,
for example `murmansk-2026-10-21.txt`, then commit and push. Several warnings in one file is fine.

Each warning starts with its header, e.g. `ПРИП МУРМАНСК 206/26`. Coordinates like
`74-00.0С 050-00.0В` are read as north/east. A warning stays on the map until its
`ОТМ ЭТОТ НР` time, or until a later PRIP cancels it with `ОТМ ... NNN/YY`.
