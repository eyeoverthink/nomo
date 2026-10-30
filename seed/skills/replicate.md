# Replication

`python nomo.py replicate <name>` copies this repository into `children/<name>`.

The copy receives the code and the seed. It receives an empty vault, no virtualenv, and no journal. `PARENT.txt` records the parent directory. The child process stays stopped until the operator starts it.
