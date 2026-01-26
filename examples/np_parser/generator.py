from . import parser

cases = [
"+nom",
"+gen",
"+par",
"+ess",
"+abe",
"+tra",
"+ade",
"+abl",
"+all",
"+ine",
"+ela",
"+ill",
]

posses = [
	"+poss1sg",
	"+poss2sg",
	"+poss1pl",
	"+poss2pl",
	"+poss3"
]

def generate_all(term: str) -> list[str]:
	res: list[str] = []
	tags = []
	for poss in posses + [""]:
		for case in cases:
			for plurality in "+sg", "+pl":
				tags.append((case, plurality, poss))
		for case in ("+ins", "+com"):
			tags.append((case, "+pl", poss))
	for case, plurality, poss in tags:
		print(term, plurality, case, poss)
		for x in parser.reinflect(term, plurality, case, poss):
			if x not in res:
				res.append(x)
	return res


if __name__ == "__main__":
	while True:
		print(generate_all(input(">> ")))