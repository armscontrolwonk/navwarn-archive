# FAA NOTAM exports go here

The FAA NOTAM Search site blocks scripts, so NOTAMs are fed by hand.

1. Open https://notams.aim.faa.gov/notamSearch/nsapp.html#/ and choose a Location search.
2. Paste a list of FIR codes from below into the Location(s) box and search.
3. Select all results, then download as Excel.
4. Drop the .xlsx file in this folder, unchanged. A .csv saved from it also works.
5. Commit and push. The next scheduled run parses it and moves it to raw/faa_notam/.

NOTAMs stay on the map until their C) end time, or until a later NOTAM replaces or cancels them.
A file that yields no NOTAMs stays here and the run log says so.

## Russian flight regions and area control centres

```
UHWW USPP UEEE USUU UEMH UENN UESS UESU UEVV UGEE UGGG UHBI UHHH UHMI UHMM UHMP UHNN UHPT UHPU UHSH UIII UIKB UIKK ULLL ULOL UMKK UNKL UNLL UNNT UOTT URFV URRV USDK USHB USHH USSV USTV UUWV UUYW UUYY UWOO UWWW UUUU URRR USSS USRR UUDD ULAA UMMS UUBW UUDL UNKL USRK UHPP UHSM UHMD ULAM UUEE UUWW UWKD 
```

## Turkey and neighbours (watch these ahead of İğneada and Black Sea launches)

```
LTAA LTBB UGGG UDDD UBBA LCCC LGGG LBSR LRBB OIIX OSTT LLLL
```
