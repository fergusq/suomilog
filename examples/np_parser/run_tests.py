import os
import difflib
import rich

from . import parser

def main():
	ok = 0
	total = 0
	path = os.path.dirname(os.path.realpath(__file__))
	with open(os.path.join(path, "test_cases.tsv")) as file:
		for line in file:
			line = line.strip()
			if line == "":
				continue

			phrase, pl, case, gold = line.split("\t")
			inflected = parser.reinflect(phrase, pl, case)
			if len(inflected) == 0:
				best = ""
			
			else:
				best = inflected[0].replace(" ,", ",")

			rich.print("[b]===")
			print(phrase)
			print(pl + case + " -> " + best)

			if best == gold:
				rich.print("[b green] OK")
				ok += 1
			else:
				rich.print("[b red] VIRHE")
				print("\n".join(difflib.unified_diff(gold.split(), best.split())))
			
			total += 1

	error = total - ok
	if error == 0:
		rich.print(f"[b green]{ok} ok[/b green] ({total} yhteensä)")
	else:
		rich.print(f"[b green]{ok} ok[/b green], [b red]{error} virhe{"ttä" if error > 1 else ""}[/b red] ({total} yhteensä)")


if __name__ == "__main__":
	main()