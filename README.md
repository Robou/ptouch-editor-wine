# P-touch Editor 6 on Linux with a Brother PT-P700

Print from Brother's own label editor, **P-touch Editor 6**, running under Wine, to a **PT-P700**
label printer connected to a Linux machine. No Windows virtual machine.

Brother ships no Linux driver for this printer, and Wine cannot load the Windows one, so Editor
normally reports that no printer driver is installed. This project registers a printer in Wine that
Editor accepts as a PT-P700, and converts what Editor prints into the printer's native raster
commands.

This is an independent project, not affiliated with or endorsed by Brother.

## Status

It works, on one setup. Labels printed from Editor 6 come out correctly oriented, positioned and
cut, and at the length Editor's preview shows (the printer pads labels shorter than 24.5 mm, see
[Limitations](#limitations)).

Tested with:

| | |
|---|---|
| Printer | PT-P700 over USB |
| Tapes | TZe 9 mm and 24 mm |
| Labels | automatic length, 1 and 2 copies |
| Editor | P-touch Editor 6.7.0 |
| System | Ubuntu 22.04, Wine 11.0, Python 3.8, Ghostscript 9.55 |

Everything outside that table is untested. Read [Limitations](#limitations) before relying on it.

## Requirements

- Wine, with P-touch Editor 6 already installed in the prefix. Installing Editor is not covered
  here; on the test machine it was installed under Wine 11.0.
- Python 3.8 or later and Ghostscript (`gs`).
- A CUPS queue for the printer, named `PT-P700` by default. Jobs are sent to it in raw mode, so the
  driver attached to the queue does not matter. The tested queue was created from the system
  printer settings with the `printer-driver-ptouch` package installed.
  Alternatively, write access to `/dev/usb/lp0` (untested).
- The printer's **Editor Lite** light must be off. With it on, the printer presents itself as a USB
  drive, not as a printer.

## Install

```sh
git clone <this repository>
cd <this repository>/wine-printer
./install.py
```

This adds a printer named `Brother PT-P700` to the Wine prefix (`$WINEPREFIX`, or `~/.wine`). It
writes a PPD file into the prefix and a few registry keys, nothing else. Restart Editor afterwards.

The spooler command is registered with its absolute path, so run `./install.py` again if you move
the directory.

Options:

| Option | Meaning |
|---|---|
| `--tape ID` | Tape selected by default: `257` 6 mm, `258` 9 mm (default), `259` 12 mm, `260` 18 mm, `261` 24 mm |
| `--spool COMMAND` | Command that receives the print job instead of `ptp700-print` |
| `--uninstall` | Remove the printer from the prefix |

## Use

1. Switch the printer on and plug it in. `lsusb | grep -i brother` should list it.
2. Start Editor:
   ```sh
   wine "C:\Program Files (x86)\Brother\P-touch Editor\6\PtouchEditor6.Wpf.exe"
   ```
3. Pick `Brother PT-P700`, choose the tape width by hand, design, print.

If the printer is off when you print, the job waits in the CUPS queue and prints when the printer
comes back.

Each job is logged in `~/.local/state/ptp700/ptp700.log`. The same directory keeps the last job as
received (`last-job.ps`), as sent (`last-job.bin`) and as a bitmap of what reaches the print head
(`last-job.pbm`).

### Settings

`ptp700-print` is started by Wine, so its settings are environment variables, set when launching
Editor. Only the defaults have been tested on the printer.

| Variable | Effect |
|---|---|
| `PTP700_QUEUE` | CUPS queue to send to (default `PT-P700`) |
| `PTP700_DEVICE` | Write straight to a device such as `/dev/usb/lp0` instead of CUPS |
| `PTP700_OUTPUT` | Write the raster commands to a file instead of printing |
| `PTP700_LENGTH` | `lbx` (default: follow the label file), `auto`, `page`, or a length in mm |
| `PTP700_NO_CUT=1` | No automatic cut |
| `PTP700_CHAIN=1` | Chain printing: no feed and cut after the last label |
| `PTP700_MIRROR=1` | Mirror printing |
| `PTP700_NO_TAPE_CHECK=1` | Do not ask the printer to check the tape width |

## Limitations

**Coverage**

- Only the PT-P700. The PT-H500 and PT-E500 use the same command set but are not set up here.
- Only TZe 9 mm and 24 mm tapes have been printed. Other widths and heat-shrink tubes are defined
  from Brother's documentation but untested.
- Verified on Wine 11.0 only. The approach depends on details of Wine's PostScript driver (see
  below) that may differ in other versions.

**Things Editor offers that do not work**

- **Print dialog options are ignored**: auto cut, chain printing, mirror printing, special tape.
  Auto cut is always on. Use the environment variables above instead.
- **"Detect media" fails** with "printer not connected". It talks to the printer through a
  Windows-only USB path. Choose the tape width manually.
- **No feedback from the printer.** Out of tape, cover open, wrong tape: none of it reaches Editor.
  The job is sent one way through CUPS.
- **Formats spanning several strips** ("24 mm x 2" and similar) are rejected.

**Label length**

- Wine's PostScript driver imposes the page length from the PPD (100 mm) whatever Editor asks for.
  `ptp700-print` recovers the intended length from the copy of the label that Editor saves when
  printing: for automatic-length labels it trims the blank end so both margins match. That case is
  the tested one.
- Fixed-length labels are untested. Labels longer than 100 mm are untested and probably truncated.

**Tape width check**

- The job asks the printer to refuse tape of a different width than the one chosen in Editor. This
  has not been tried on the printer.

**Printer behaviour, not caused by this project**

- The cutter sits about 24.5 mm after the print head, so no piece shorter than 24.5 mm comes out: a
  shorter label is printed on 24.5 mm of tape.
- For the same reason, each job starts by cutting off a blank piece of about 24.5 mm. There is one
  per job, not one per copy. Chain printing is Brother's way to avoid it, untested here.

## How it works

```
P-touch Editor 6 ──► Wine printer "Brother PT-P700" ──► ptp700-print ──► CUPS queue (raw) ──► printer
                     (Wine's PostScript driver            Ghostscript at 180 dpi,
                      with a purpose-made PPD)            Brother raster commands
```

Editor renders the label itself, as a bitmap at the printer's resolution. It only needs a Windows
printer it recognises to print to. Four things make Wine's generic PostScript printer pass for one:

1. **The driver name.** Editor matches printers by driver name, so the printer and its driver are
   both called exactly `Brother PT-P700`.
2. **180 dpi in the default settings.** Wine's PostScript driver hard-codes 300 dpi. Editor then
   finds no matching resolution for a PT-P700 and crashes with a `NullReferenceException` when you
   press Print. `install.py` stores default settings at 180 dpi, and the PPD declares a `Duplex`
   option because Wine discards stored settings for printers without one.
3. **Brother's paper IDs.** Editor selects the tape by Brother's numeric paper size (258 for 9 mm,
   261 for 24 mm). Wine numbers unknown PPD page sizes from 256 in file order, so `make_ppd.py`
   pads the PPD with reserved entries until each tape lands on its Brother ID.
4. **The `Devices` and `PrinterPorts` registry entries**, which Wine normally writes itself when it
   imports a CUPS printer. Without them `CreateDC` fails silently.

The Wine printer's port is redirected to `ptp700-print`, which rasterises the PostScript with
Ghostscript and builds the job described in Brother's
[Raster Command Reference for the PT-H500/P700/E500](https://download.brother.com/welcome/docp000771/cv_pth500p700e500_eng_raster_111.pdf).

## Files

| File | Role |
|---|---|
| `wine-printer/install.py` | Registers or removes the printer in the Wine prefix |
| `wine-printer/make_ppd.py` | Generates the PPD; holds the tape table |
| `wine-printer/ptp700-print` | Turns a print job into raster commands and sends it |
| `wine-printer/spool-capture.sh` | Debug: saves print jobs instead of printing them |
| `tests/decode_job.py` | Decodes a raster command stream back into text and a bitmap |
| `tests/sample-24mm-2-copies.ps` | A job captured from Editor |

Code comments and messages are in French.

## Checking without a printer

```sh
wine-printer/ptp700-print --length auto --output /tmp/job.bin < tests/sample-24mm-2-copies.ps
tests/decode_job.py /tmp/job.bin /tmp/job.pbm
```

The decoder lists the commands in the job (two labels of 29 raster lines for the sample) and writes
the bitmap the print head would receive.

## Troubleshooting

- **Nothing prints.** Check `lsusb | grep -i brother`. If the printer is missing, it is off, on a
  charge-only cable, or not plugged into a USB port. If it is listed, check that the Editor Lite
  light is off, then look at `lpstat -p PT-P700` and the log.
- **Editor says no printer driver is installed.** The printer is missing from this Wine prefix: run
  `./install.py` with the same `WINEPREFIX` you start Editor with.
- **Editor crashes when you press Print.** The stored settings are not at 180 dpi; run
  `./install.py` again and restart Editor.

## Related projects

These replace Brother's editor instead of running it:

- [ptouch-print](https://github.com/torbenwendt/ptouch-print): command-line printing of text and
  images. Its source was the reference for the bit order on the print head.
- [printer-driver-ptouch](https://github.com/philpem/printer-driver-ptouch): CUPS driver for P-touch
  and QL printers.
