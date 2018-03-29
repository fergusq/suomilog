# Suomilog
# Copyright (C) 2018 Iikka Hauhio
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import readline, os
from suomilog.patternparser import PATTERNS, setDebug, PatternRef, parseGrammarLine as pgl, matchAll
from suomilog.finnish import tokenize

class AnyPattern:
	def __repr__(self):
		return "AnyPattern()"
	def toCode(self):
		return "<pattern that matches all strings without punctuation>"
	def match(self, tokens, bits):
		for token in tokens:
			if token.token in [".", ",", ":", "!", "?"]:
				return []
		return [[lambda: tokens, " ".join([t.token for t in tokens])]]

PATTERNS["*"] = [
	AnyPattern()
]

class StringContentPattern:
	def __repr__(self):
		return "StringContentPattern()"
	def toCode(self):
		return "<pattern that matches all strings without quote marks>"
	def match(self, tokens, bits):
		for token in tokens:
			if token.token == '"':
				return []
		string = " ".join([t.token for t in tokens])
		return [[lambda: string, string]]

PATTERNS["STR-CONTENT"] = [
	StringContentPattern()
]

class FuncOutput:
	def __init__(self, f):
		self.func = f
	def eval(self, args):
		return lambda: self.func(*[arg() for arg in args])

identity = FuncOutput(lambda x: x)

def nameToBaseform(tokens, bits, rbits):
	ans = []
	found = False
	for token in reversed(tokens):
		for bf, tbits in token.alternatives:
			if not found:
				if rbits <= tbits:
					ans.append((bf, bits or {"$"}))
					found = True
					break
			else:
				if rbits <= tbits and ("laatusana" in tbits or "nimisana_laatusana" in tbits or "agent" in tbits):
					ans.append((bf, bits or {"$"}))
					break
		else:
			ans.append((token.token, set()))
	return reversed(ans)

def tokensToString(tokens, rbits={"nimento"}):
	return " ".join([text for text, bits in nameToBaseform(tokens, {}, rbits)])

def nameToCode(name, bits=None, rbits={"nimento"}):
	return " ".join([token + ("{" + ",".join(tbits) + "}" if tbits else "") for token, tbits in nameToBaseform(name, bits, rbits)])

# Luokat

counter = 0

class RObject:
	def __init__(self, rclass):
		self.rclass = rclass
		self.data = {}
		self.extra = {}
	def get(self, field_name):
		if field_name not in self.data:
			self.data[field_name] = self.rclass.fields[field_name].default_value
		return self.data[field_name]
	def setExtra(self, name, data):
		self.extra[name] = data
		return self
	def asString(self):
		return "[eräs " + self.rclass.name + "]"

class RClass:
	def __init__(self, name, superclass):
		global counter
		counter += 1
		
		self.id = counter
		self.name = name
		self.superclass = superclass
		self.direct_subclasses = []
		self.fields = {}
		
		if superclass:
			self.superclass.direct_subclasses.append(self)
	def newInstance(self):
		return RObject(self)
	def superclasses(self):
		if self.superclass == None:
			return [self]
		else:
			return [self] + self.superclass.superclasses()
	def subclasses(self):
		ans = [self]
		for subclass in self.direct_subclasses:
			ans += subclass.subclasses()
		return ans

class RField:
	def __init__(self, counter, name, vtype, defa=None):
		self.id = counter
		self.name = name
		self.type = vtype
		self.default_value = defa or ei_mikään
	def copy(self):
		return RField(self.counter, self.name, self.vtype, self.default_value)

def defineClass(name, superclass):
	_defineClass(tokensToString(name), nameToCode(name), superclass)
def _defineClass(name_str, name_code, superclass):
	rclass = RClass(name_str, superclass)
	for clazz in reversed(superclass.superclasses()) if superclass else []:
		for fname in clazz.fields:
			rclass.fields[fname] = clazz.fields[fname].copy()
	for clazz in rclass.superclasses():
		pgl(".CLASS-%d ::= %s -> %s" % (clazz.id, name_code, name_str), FuncOutput(lambda: rclass))
	pgl(".CLASS ::= %s -> %s" % (name_code, name_str), FuncOutput(lambda: rclass))
	return rclass

pgl(".CLASS-DEF ::= .* on käsite . -> class $1 : asia", FuncOutput(lambda x: defineClass(x, asia)))
pgl(".CLASS-DEF ::= .* on .CLASS{omanto} alakäsite . -> class $1 : $2", FuncOutput(defineClass))
pgl(".DEF ::= .CLASS-DEF -> $1", identity)

# Sisäänrakennetut luokat

asia = _defineClass("asia", "asia{$}", None)

ei_mikään = asia.newInstance()
pgl(".EXPR-%d ::= ei-mikään{$} -> ei-mikään" % (asia.id,), FuncOutput(lambda: ei_mikään))

merkkijono = _defineClass("merkkijono", "merkkijono{$}", asia)
pgl('.EXPR-%d ::= " .STR-CONTENT " -> "$1"' % (merkkijono.id,), FuncOutput(lambda x: merkkijono.newInstance().setExtra("str", x)))

# Ominaisuudet

def defineField(owner, name, vtype, case="nimento"):
	name_str = tokensToString(name, {"yksikkö", case})
	global counter
	counter += 1
	for clazz in owner.subclasses():
		field = RField(counter, name_str, vtype)
		clazz.fields[name_str] = field
	for clazz in vtype.superclasses():
		pgl(".EXPR-%d ::= .EXPR-%d{omanto} %s -> $1.%s" % (clazz.id, owner.id, nameToCode(name, rbits={"nimento", "yksikkö"}), name_str), FuncOutput(lambda obj: obj.get(name_str)))
	def setDefaultValue(clazz, defa):
		clazz.fields[name_str].default_value = defa
	pgl(".FIELD-DEFAULT-DEF-%d ::= .CLASS-%d{omanto} %s on yleensä .EXPR-%d . -> $1.%s defaults $2" % (
		field.id, owner.id, nameToCode(name, {"nimento"}, rbits={case, "yksikkö"}), vtype.id, name_str
		), FuncOutput(setDefaultValue))
	pgl(".DEF ::= .FIELD-DEFAULT-DEF-%d -> $1" % (field.id,), identity)

pgl(".FIELD-DEF ::= .CLASS{ulkoolento} on .* , joka on .CLASS{nimento} . -> $1.$2 : $3", FuncOutput(defineField))
pgl(".FIELD-DEF ::= .CLASS{ulkoolento} on .* kutsuttu .CLASS{nimento} . -> $1.$2 : $3", FuncOutput(lambda *x: defineField(*x, case="tulento")))
pgl(".DEF ::= .FIELD-DEF -> $1", identity)

# Muuttujat

VARIABLES = {}

def defineVariable(name, vtype):
	name_str = tokensToString(name)
	VARIABLES[name_str] = vtype.newInstance()
	for clazz in vtype.superclasses():
		pgl(".EXPR-%d ::= %s -> %s" % (clazz.id, nameToCode(name), name_str), FuncOutput(lambda: VARIABLES[name_str]))

pgl(".VARIABLE-DEF ::= .* on .CLASS{nimento} . -> $1 : $2", FuncOutput(defineVariable))
pgl(".DEF ::= .VARIABLE-DEF -> $1", identity)

# Tulostaminen

def printCommand(value):
	if value.rclass is merkkijono:
		print(value.extra["str"])
	else:
		print(value.asString())

pgl(".CMD ::= sano .EXPR-%d{nimento} . -> print($1)" % (asia.id,), FuncOutput(printCommand))

# Pääohjelma

def main():
	def complete_file(t, s):
		path, file = os.path.split(t)
		for i, f in enumerate(filter(lambda f: f.startswith(file), os.listdir(path or "."))):
			if i == s:
				return os.path.join(path, f)
	readline.set_completer(complete_file)
	readline.set_completer_delims(" ")
	readline.parse_and_bind('tab: complete')

	def printStatistics():
		n_patterns = sum([len(category) for category in PATTERNS.values()])
		print("Ladattu", n_patterns, "fraasia.")
	printStatistics()
	while True:
		try:
			line = input(">> ")
		except EOFError:
			break
		if not line:
			continue
		if line == "/kielioppi":
			for category in sorted(PATTERNS):
				print(category, "::=")
				for pattern in PATTERNS[category]:
					print(" " + pattern.toCode())
			continue
		elif line == "/käsitteet":
			def printClass(clazz, indent):
				print(" "*indent + clazz.name + "{" + ", ".join(sorted(clazz.fields.keys())) + "}")
				for subclass in sorted(clazz.direct_subclasses, key=lambda c: c.name):
					printClass(subclass, indent+1)
			printClass(asia, 0)
			continue
		elif line == "/debug 0":
			setDebug(0)
			continue
		elif line == "/debug 1":
			setDebug(1)
			continue
		elif line == "/debug 2":
			setDebug(2)
			continue
		elif line == "/debug 3":
			setDebug(3)
			continue
		elif line.startswith("/eval"):
			print(eval(line[5:].strip()))
			continue
		elif line.startswith("/lataa"):
			file = line[6:].strip()
			with open(file) as f:
				for l in f:
					a = matchAll(tokenize(l.strip()), "DEF", set())
					if len(a) == 1:
						a[0][0]()
					else:
						print("Virhe ladattaessa tiedostoa.")
			printStatistics()
			continue
		phrase_type = "DEF"
		if line[0] == "!":
			phrase_type = "CMD"
			line = line[1:]
		interpretations = matchAll(tokenize(line), phrase_type, set())
		if len(interpretations) == 0:
			print("Ei tulkintaa.")
		elif len(interpretations) == 1:
			print(interpretations[0][1])
			interpretations[0][0]()
		else:
			print("Löydetty", len(interpretations), "tulkintaa:")
			for _, interpretation in interpretations:
				print(interpretation)
		printStatistics()
			

if __name__ == "__main__":
	main()
