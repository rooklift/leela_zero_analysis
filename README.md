# leela_zero_analysis
SGF --> Leela Zero analysis (simple)

Analysis script for SGF files using [Leela Zero](http://zero.sjeng.org/).

* Requires [gofish](https://github.com/fohristiwhirl/gofish) library (which I've included in this repo).
* Requires Leela Zero 0.17.
* The `config.json` file will need to be altered for anyone else's machine.

The `lza.py` script will create a new SGF file with winrates and preferred moves.

Afterwards, the new SGF file can also be passed to `graph.py` to create a winrate graph:

![winrate](https://user-images.githubusercontent.com/16438795/56060841-de0a3d00-5d5f-11e9-827d-5cdb9df189ab.png)
