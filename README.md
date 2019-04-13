Analysis script for SGF files using [Leela Zero](http://zero.sjeng.org/).

* Requires [gofish](https://github.com/fohristiwhirl/gofish) library (which I've included in this repo).
* Requires Leela Zero 0.17.
* The `config.json` file will need to be altered for anyone else's machine.

The `lza.py` script will create a new SGF file with winrates and preferred moves.

Afterwards, the new SGF file can also be passed to `graph.py` to create a winrate graph:

![winrate](https://user-images.githubusercontent.com/16438795/56061623-da77b580-5d61-11e9-8f4e-852adf90b9a7.png)
