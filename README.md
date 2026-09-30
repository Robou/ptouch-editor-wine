# ptouch-editor-wine: Brother P-touch Editor 6 on Linux (Wine) with a PT-P700

Use Brother's own label software, **P-touch Editor 6**, on Linux and print to a **PT-P700** label
printer. Editor runs under Wine; no Windows virtual machine is needed.

Out of the box this does not work: Brother has no Linux driver for the PT-P700 and Wine cannot use
the Windows one, so Editor says `There is no printer driver installed with this application.`
This project adds the missing piece.

It has been tested on one setup: Ubuntu 22.04, Wine 11.0, P-touch Editor 6.7, a PT-P700 over USB,
with 9 mm and 24 mm TZe tape. It is an independent project, not affiliated with Brother.

## Install

### 1. System packages

```sh
sudo apt install cups printer-driver-ptouch ghostscript python3 git
```

`printer-driver-ptouch` is required: it is what lets the Linux printing system (CUPS) handle the
PT-P700.

You also need Wine. Version 11.0 from [WineHQ's repository](https://gitlab.winehq.org/wine/wine/-/wikis/Download)
is the tested one.

### 2. The printer

Switch the printer on, make sure its **Editor Lite** light is off, and plug it in.

```sh
lsusb | grep -i brother      # the printer must be listed
lpstat -v                    # look for a printer named PT-P700
```

If `lpstat -v` shows no `PT-P700`, add it from your desktop's printer settings, naming it
`PT-P700`, or with:

```sh
sudo lpadmin -p PT-P700 -E \
  -v "$(sudo lpinfo -v | grep -o 'usb://Brother/PT-P700[^ ]*')" \
  -m ptouch:0/ppd/ptouch-driver/Brother-PT-P700-ptouch-pt.ppd
```

### 3. P-touch Editor 6

Download P-touch Editor 6 for Windows from
[Brother's support site](https://support.brother.com/g/b/downloadtop.aspx?c=us&lang=en&prod=p700eus)
and run the installer with Wine:

```sh
wine pew6xxxx.exe
```

You do not need Brother's Windows printer driver.

### 4. This project

```sh
git clone https://github.com/Robou/ptouch-editor-wine.git
cd ptouch-editor-wine/wine-printer
./install.py
```

This adds a printer called `Brother PT-P700` to Wine. Do not move the `ptouch-editor-wine` folder
afterwards, or run `./install.py` again if you do.

To remove it: `./install.py --uninstall`.

## Use

```sh
wine "C:\Program Files (x86)\Brother\P-touch Editor\6\PtouchEditor6.Wpf.exe"
```

Select `Brother PT-P700`, **choose the tape width yourself**, design your label and print.

If the printer is off when you print, the label waits and comes out when you switch it back on.

## Limitations

- **Only the PT-P700**, and only 9 mm and 24 mm TZe tapes have actually been printed.
- **The options in Editor's print window have no effect** (auto cut, chain printing, mirror
  printing). Labels are always cut automatically.
- **"Detect media" does not work.** Choose the tape width by hand.
- **Editor is not told about printer problems** such as no tape or an open cover. The label simply
  does not come out.
- **Long and fixed-length labels are untested.** Labels longer than 100 mm are probably cut short.
- **Formats that span several strips** ("24 mm x 2" and similar) are not supported.

Two things you will notice come from the printer itself, not from this project:

- No label can be shorter than about 24.5 mm.
- Each print job starts by cutting off a blank piece of about 24.5 mm.

## If something goes wrong

- **Nothing prints.** Run `lsusb | grep -i brother`. If the printer is not listed, it is off, on a
  charge-only USB cable, or not plugged into a USB port. If it is listed, check that the Editor Lite
  light is off, then run `lpstat -p PT-P700`.
- **Editor says no printer driver is installed.** Run `./install.py` again, with the same
  `WINEPREFIX` you start Editor with if you use one.
- **Editor crashes when you press Print.** Run `./install.py` again and restart Editor.

Each print is logged in `~/.local/state/ptp700/ptp700.log`.

---

# Details

The rest is for people who want to tune, debug or extend the project.

## Symptoms this fixes

These are the messages you get when running P-touch Editor 6 under plain Wine:

- `There is no printer driver installed with this application.`
- A crash when pressing Print: Wine reports
  `Unhandled exception: page fault on read access to 0x00000008`, and the log shows
  `System.NullReferenceException` in `PtouchEditor6.Wpf.ViewModels.PrintSettingViewModel`.
- Printing does nothing and Wine logs `err:gdi:CreateDCW no driver found for L"WINSPOOL"`.

There is no way to install Brother's Windows printer driver instead: Wine does not load Windows
printer drivers.

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
   finds no matching resolution for a PT-P700 and crashes when you press Print. `install.py` stores
   default settings at 180 dpi, and the PPD declares a `Duplex` option because Wine discards stored
   settings for printers without one.
3. **Brother's paper IDs.** Editor selects the tape by Brother's numeric paper size (258 for 9 mm,
   261 for 24 mm). Wine numbers unknown PPD page sizes from 256 in file order, so `make_ppd.py`
   pads the PPD with reserved entries until each tape lands on its Brother ID.
4. **The `Devices` and `PrinterPorts` registry entries**, which Wine normally writes itself when it
   imports a CUPS printer. Without them `CreateDC` fails silently.

The Wine printer's port is redirected to `ptp700-print`, which rasterises the PostScript with
Ghostscript and builds the job described in Brother's
[Raster Command Reference for the PT-H500/P700/E500](https://download.brother.com/welcome/docp000771/cv_pth500p700e500_eng_raster_111.pdf).
The job goes to the CUPS queue in raw mode, so the queue's own driver is not involved in printing.

## Settings

`install.py` options:

| Option | Meaning |
|---|---|
| `--tape ID` | Tape selected by default: `257` 6 mm, `258` 9 mm (default), `259` 12 mm, `260` 18 mm, `261` 24 mm |
| `--spool COMMAND` | Command that receives the print job instead of `ptp700-print` |
| `--uninstall` | Remove the printer from the Wine prefix |

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

## More on the limitations

- **Other printers.** The PT-H500 and PT-E500 use the same command set but are not set up here.
- **Other tapes.** Widths other than 9 and 24 mm, and heat-shrink tubes, are defined from Brother's
  documentation but untested.
- **Other Wine versions.** The approach depends on details of Wine's PostScript driver, verified in
  Wine 11.0 only.
- **Label length.** Wine's PostScript driver imposes the page length from the PPD (100 mm) whatever
  Editor asks for. `ptp700-print` recovers the intended length from the copy of the label that
  Editor saves when printing; for automatic-length labels it trims the blank end so both margins
  match. Automatic length is the tested case.
- **Tape width check.** The job asks the printer to refuse a tape of a different width than the one
  chosen in Editor. This has not been tried on the printer.
- **Print options and media detection.** How Editor hands its print options to Brother's driver
  has not been investigated; nothing of them reaches `ptp700-print`, which is why the environment
  variables above exist. Media detection goes through a Windows-only USB path.
- **The blank piece at the start of each job.** The cutter sits about 24.5 mm after the print head.
  Chain printing is Brother's way to avoid the waste; it is untested here.

## Files and debugging

| File | Role |
|---|---|
| `wine-printer/install.py` | Registers or removes the printer in the Wine prefix |
| `wine-printer/make_ppd.py` | Generates the PPD; holds the tape table |
| `wine-printer/ptp700-print` | Turns a print job into raster commands and sends it |
| `wine-printer/spool-capture.sh` | Saves print jobs instead of printing them |
| `tests/decode_job.py` | Decodes a raster command stream back into text and a bitmap |
| `tests/sample-24mm-2-copies.ps` | A job captured from Editor |

`~/.local/state/ptp700/` keeps the log and the last job as received (`last-job.ps`), as sent
(`last-job.bin`) and as a bitmap of what reaches the print head (`last-job.pbm`).

To check the conversion without a printer:

```sh
wine-printer/ptp700-print --length auto --output /tmp/job.bin < tests/sample-24mm-2-copies.ps
tests/decode_job.py /tmp/job.bin /tmp/job.pbm
```

The decoder lists the commands in the job (two labels of 29 raster lines for the sample) and writes
the bitmap the print head would receive.

## License

GPL-3.0-or-later, see [LICENSE](LICENSE). You may use, modify and redistribute this code; if you
distribute a modified version, it must stay under the same license and credit the original.

## Credits

- [ptouch-print](https://github.com/torbenwendt/ptouch-print), whose source was the reference for
  the bit order on the print head.
- [printer-driver-ptouch](https://github.com/philpem/printer-driver-ptouch), the CUPS driver this
  project relies on.

---

# Don't need Brother's editor? Try ptouch-rs

If what you want is simply to print good labels from Linux, have a look at
**[ptouch-rs](https://github.com/vowstar/ptouch-rs)**, an excellent independent project.

It is a native application with both a graphical editor and a command-line tool, written in Rust,
for Brother P-touch USB printers, the PT-P700 included. It talks to the printer directly, with no
Wine and no Windows software, and runs on Linux, macOS and Windows. It offers text with custom
fonts, images, a live preview, saved designs, templates with batch printing from CSV files, and
ready-made `.deb` and `.rpm` packages.
