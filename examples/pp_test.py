import readline, os

from suomilog.patternparser import *
from suomilog.finnish import tokenize

query = Pattern("QUERY", [
	Token("hae", "", set()),
	Token("jokainen", "", set()),
	PatternRef("PATTERN", {"nimento", "yksikkö"})
], StringOutput("search($1)"))

path = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(path, "employees.txt")) as file:
	for line in file:
		if "::=" in line:
			parseGrammarLine(line.replace("\n", ""))

n_patterns = sum([len(category) for category in PATTERNS.values()])

print("Ladattu", n_patterns, "fraasia.")

while True:
	try:
		line = input(">> ")
	except EOFError:
		print()
		break
	if not line:
		continue
	elif line[0] == ".":
		line = line.replace("\t", " ")
		tokens = line.split(" ")
		if len(tokens) == 1 and tokens[0][1:] in PATTERNS:
			print(PATTERNS[tokens[0][1:]])
		elif len(tokens) > 2 and tokens[1] == "::=" and "->" in tokens:
			parseGrammarLine(line)
		else:
			print("Kategoriat:")
			for cat in PATTERNS:
				print(cat)
	else:
		tokens = tokenize(line)
		for alt in query.match(tokens, set()):
			print(alt)
