<div align="center">

# pwk

[![License](https://img.shields.io/badge/LICENSE-MIT-5C9E31?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/PYTHON-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![Built by](https://img.shields.io/badge/BUILT%20BY-JGALEA-8A2BE2?style=for-the-badge&logo=github&logoColor=white)](https://github.com/jgalea)

**Find things to do with your kids in Portugal, from the terminal.**

</div>

An unofficial command-line client for [portugalwithkids.pt](https://portugalwithkids.pt/),
a directory of 556 kid-friendly places and several thousand dated events across Portugal.

The site has no radius search, so finding what is actually near you means clicking
through categories. Its text search matches words rather than locations: searching
"Cascais" returns 9 results where a 30km radius around the same town finds 63. Every
listing carries coordinates, so `pwk` caches them and sorts by distance.

## Install

Python 3.9+, no dependencies. On a Mac or Linux:

    git clone https://github.com/jgalea/pwk.git
    ln -s "$PWD/pwk/pwk.py" ~/.local/bin/pwk

On Windows, in PowerShell, install Python if you don't have it
(`winget install Python.Python.3.12`), open a new window, and run:

    mkdir "$HOME\pwk" -Force
    curl.exe -fsSL https://raw.githubusercontent.com/jgalea/pwk/main/pwk.py -o "$HOME\pwk\pwk.py"
    mkdir "$HOME\bin" -Force
    Set-Content "$HOME\bin\pwk.cmd" '@py "%USERPROFILE%\pwk\pwk.py" %*'
    [Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path", "User") + ";$HOME\bin", "User")

Open a new PowerShell window after that so `pwk` is on the PATH. The Windows steps
haven't been tested on a real Windows machine yet.

The place cache is kept in a `cache` folder next to `pwk.py`.

Set a default origin so you can stop typing it:

    export PWK_ORIGIN=porto        # a town name, or "41.15,-8.62"

On Windows that's `[Environment]::SetEnvironmentVariable("PWK_ORIGIN", "porto", "User")`.

## Usage

Places near you, nearest first:

    pwk near                       # 20 nearest within 25km
    pwk near -r 40 -n 30
    pwk near -o sintra -r 15
    pwk near -o 38.69,-9.42        # anywhere, by coordinates

Filter them:

    pwk near -c playground         # category, English alias or Portuguese name
    pwk near --indoor              # rainy day
    pwk near --outdoor --free
    pwk near -k praia

What is on, by date:

    pwk events                     # today through the next week, nationally
    pwk events -w weekend --where lisbon
    pwk events -w tomorrow --where porto
    pwk events -w 2026-09-05:2026-09-07 -k teatro

Detail for one place, and what is available near you:

    pwk show "quinta do pisao"     # hours, prices, phone, map link
    pwk cats -r 30

The place cache refreshes on first run and tells you when it is over 30 days old.
`pwk refresh` re-pulls it.

## Notes

Categories are Portuguese. `-c` also accepts English aliases: playground, beach,
farm, museum, pool, waterpark, zoo, aquarium, workshop, castle, garden, library,
theatre, climbing, trail, dinosaur, horse, science.

`--indoor` and `--outdoor` are inferred from a listing's categories here. The site
has no such field, so treat them as a first cut rather than the last word.

Event venues carry a city but no coordinates, so `events` filters by city name
while `near` uses a real radius. `--where lisbon` covers the surrounding councils,
Sintra and Oeiras included.

Coverage is densest around Lisbon and Porto and thins in between. Some listings
have no opening hours or prices, because the site does not have them either.

## Data

All listing data belongs to Portugal With Kids. This tool only reads their public
API on your machine and caches it locally; it does not republish or host any of
their content, and the cache is not part of this repository. If you find the
directory useful, visit the site: it is where the work was done.

Not affiliated with, endorsed by, or supported by Portugal With Kids.
