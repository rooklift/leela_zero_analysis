import gofish, os, subprocess, sys, time

# -------------

leela_zero = "C:\\Programs (self-installed)\\Leela Zero\\leelaz.exe"
network_dir = "C:\\Programs (self-installed)\\Leela Zero\\networks"

network = "8fc22bca11d3e913eb09989719adb8ae5256af3d157cb8db708f0660d7aafac0"
visits = 1

extras = "--gtp --noponder --resignpct 0 --threads 1"

quiet = True
debug_comms = True

# -------------

process = None

def send(msg):
	global process

	if msg.endswith("\n") == False:
		msg += "\n"
	if debug_comms:
		print("--> " + msg.strip())
	msg = bytes(msg, encoding = "ascii")
	process.stdin.write(msg)
	process.stdin.flush()

def receive_gtp():
	global process

	s = ""

	while 1:
		z = process.stdout.readline().decode("utf-8")
		if z.strip() == "":		# Blank line always means end of output (I think)
			return s.strip()
		s += z

def main():
	global process

	if len(sys.argv) == 1:
		print("Usage: {} <filename>".format(sys.argv[0]))
		sys.exit()

	node = gofish.load(sys.argv[1])

	cmd = "\"{}\" -v {} {} -w \"{}\"".format(leela_zero, visits, extras, os.path.join(network_dir, network))

	process = subprocess.Popen(cmd,
		shell = False,
		stdin = subprocess.PIPE,
		stdout = subprocess.PIPE,
		stderr = subprocess.DEVNULL if quiet else None)

	while 1:

		# If node is at end, we have nothing to do...

		child = node.main_child()
		if not child:
			break

		# If there's a move, send it to the engine...

		if node.move_coords():

			colour_foo = node.move_colour()

			if colour_foo == gofish.BLACK:
				colour = "black"
			elif colour_foo == gofish.WHITE:
				colour = "white"
			else:
				colour = "??"

			english = gofish.english_string_from_point(*node.move_coords(), node.board.boardsize)

			send("play {} {}".format(colour, english))
			receive_gtp()

		# If the child has a move, compare it to LZ's choice...

		if child.move_coords():

			last_colour_foo = node.last_colour_played()

			if last_colour_foo in [gofish.WHITE, None]:
				next_colour = "black"
			elif last_colour_foo == gofish.BLACK:
				next_colour = "white"
			else:
				next_colour = "??"

			send("genmove {}".format(next_colour))
			r = receive_gtp()
			if debug_comms:
				print("<-- {}".format(r))

			english = r.split()[1]
			point = gofish.point_from_english_string(english, node.board.boardsize)

			if point:
				sgf_point = gofish.string_from_point(*point)
			else:
				sgf_point = ""

			if child.move_coords() == point:
				child.delete_property("C")
			else:
				child.set_value("C", "LZ prefers {}".format(english))

			if sgf_point:
				child.set_value("TR", sgf_point)

			send("undo")
			receive_gtp()

		next_node = node.main_child()

		if not next_node:
			break

		node = next_node

	node.save(sys.argv[1] + ".lza.sgf")

main()
