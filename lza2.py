import gofish, json, os, subprocess, sys, threading, time

extras = "--gtp --noponder --resignpct 0 --threads 1"

config = None

class Hub:

	def __init__(self, cmd):
		self.n = 0
		self.in_id = None		# Last incoming message ID seen (e.g. when the engine sends "=7" or whatnot)
		self.process = subprocess.Popen(cmd, shell = False, stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.DEVNULL)
		# Note that the stderr needs to be consumed somehow, hence the DEVNULL here.

	def next_qid(self):
		self.n += 1
		return self.n

	def _send(self, msg):
		msg = msg.strip()
		print(msg)								# Debugging.
		msg = bytes(msg, encoding = "ascii")
		self.process.stdin.write(msg)
		self.process.stdin.write(b"\n")
		self.process.stdin.flush()

	def _receive(self):
		z = self.process.stdout.readline().decode("utf-8").strip()
		if len(z) > 0 and z[0] == "=":
			self.in_id = int(z[1:].split()[0])
		print(z)
		return z

	def send_and_receive(self, msg):

		# Add a unique ID number to the start...

		out_id = self.next_qid()
		msg = "{} {}".format(out_id, msg)

		# Send...

		self._send(msg)

		# Receive the response, ignoring any lines with a different ID.

		s = ""

		while 1:
			z = self._receive()

			if self.in_id == out_id:
				if z.strip() != "":
					s += z + "\n"
				else:
					return s			# Blank line always means end of output (I think).

	def new_analyze(self):

		out_id = self.next_qid()
		msg = "{} {}".format(out_id, "lz-analyze 100")

		self._send(msg)

		start_time = time.monotonic()

		while time.monotonic() - start_time < config["seconds"]:
			z = self._receive()

			if self.in_id == out_id:
				if "info" in z:
					pass

		self.send_and_receive("name")





class Info:

	# We'll store moves as either None or [x,y]

	def __init__(self, node):
		self.node = node
		self.colour = None
		self.best_move = None
		self.PV = None					# PV alternative to the actual move, if any
		self.score_before_move = None
		self.score_after_move = None
		self.parent = None				# Info object of previous position

	def send_AB_AW(self, hub):

		for stone in self.node.get_all_values("AB"):
			english = gofish.english_string_from_string(stone, self.node.board.boardsize)
			hub.send_and_receive("play black {}".format(english))

		for stone in self.node.get_all_values("AW"):
			english = gofish.english_string_from_string(stone, self.node.board.boardsize)
			hub.send_and_receive("play white {}".format(english))

	def send_move(self, hub):

		if self.node.move_coords():
			english_actual = gofish.english_string_from_point(*self.node.move_coords(), self.node.board.boardsize)
			hub.send_and_receive("play {} {}".format(self.colour, english_actual))


def main():

	global config

	if len(sys.argv) == 1:
		print("Usage: {} <filename>".format(sys.argv[0]))
		sys.exit()

	scriptpath = os.path.realpath(__file__)
	configfile = os.path.join(os.path.dirname(scriptpath), "config.json")
	with open(configfile) as cfg:
		config = json.load(cfg)

	cmd = "\"{}\" {} -w \"{}\"".format(config["engine"], extras, os.path.join(config["network_dir"], config["network"]))
	hub = Hub(cmd)

	hub.send_and_receive("name")			# Ensure we can communicate.

	root = gofish.load(sys.argv[1])

	# Make a list of Info objects...

	all_info = []
	node = root

	while 1:

		# Totally ignore empty nodes. Everything else gets put in the list...

		if "B" in node.properties or "W" in node.properties or "AB" in node.properties or "AW" in node.properties:

			new_info = Info(node)

			if len(all_info) > 0:
				new_info.parent = all_info[-1]		# Might not correspond to the node's actual parent node (due to empty nodes)

			if node.move_colour():
				new_info.colour = {gofish.BLACK: "black", gofish.WHITE: "white"}[node.move_colour()]

			all_info.append(new_info)

		node = node.main_child()
		if node == None:
			break

	# Main loop...

	for info in all_info:

		# Send any handicap stones etc...

		info.send_AB_AW(hub)

		hub.new_analyze()

		info.send_move(hub)


# -------------

main()
