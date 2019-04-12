# This script extracts a winrate graph from an lza.py-produced SGF file.

import sys, time
import gofish
import matplotlib.pyplot as plt

plt.style.use("dark_background")

node = gofish.load(sys.argv[1])

data = []

while 1:
	comment = node.get_value("C")
	if comment is not None:
		if "%" in comment:
			i = comment.index("%")
			pc = comment[:i]
			data.append(float(pc))
	node = node.main_child()
	if node == None:
		break

if len(data) < 2:
	print("No data")
	time.sleep(0.5)
	sys.exit()

_, ax = plt.subplots()
ax.spines["right"].set_visible(False)
ax.spines["top"].set_visible(False)
plt.xlim([0, len(data)])
plt.ylim([0, 100])
plt.ylabel("Black WR")
plt.plot(data)
plt.show()
