Analysis script for SGF files using [Leela Zero](http://zero.sjeng.org/).

* Requires [gofish](https://github.com/fohristiwhirl/gofish) library (which I've included in this repo).
* Requires Leela Zero 0.17.
* The `config.json` file will need to be altered for anyone else's machine.

The `lza.py` script will create a new SGF file with winrates and preferred moves in the comments. It also adds [Sabaki](https://github.com/SabakiHQ/Sabaki)'s `SBKV` tags, meaning that Sabaki can be used to visualise the winrate graph when used to view the SGF file.

Alternatively, the new SGF file can also be passed to `graph.py` to create a winrate graph:

![winrate](https://user-images.githubusercontent.com/16438795/56093435-c0a0b480-5ec0-11e9-9615-0ae06aa77803.png)
