# leela_zero_analysis
SGF --> Leela Zero analysis (simple)

Analysis script for SGF files in Leela Zero.

* Requires [gofish](https://github.com/fohristiwhirl/gofish) library.
* Some constants at the top of this script will need fixing for anyone else's machine.

Note to self: there's probably a race condition here somewhere since we rely on a thread reading the stderr from LZ to get the principal variation.
