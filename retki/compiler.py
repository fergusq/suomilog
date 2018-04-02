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

import readline, os, sys, argparse, traceback
import itertools
from suomilog.patternparser import ERROR_STACK, setDebug, PatternRef, Grammar
from suomilog.finnish import tokenize, CASES
from .language import *
from .tokenutils import *

GRAMMAR = Grammar()
pgl = GRAMMAR.parseGrammarLine

# Villikortit

class AnyPattern:
	def __init__(self, allow_empty):
		self.allow_empty = allow_empty
	def __repr__(self):
		return "AnyPattern()"
	def toCode(self):
		return "<pattern that matches all strings without punctuation>"
	def match(self, grammar, tokens, bits):
		for token in tokens:
			if token.token in [".", ",", ":", "!", "?", "[", "]"]:
				return []
		return [[lambda: tokens, " ".join([t.token for t in tokens])]]
	def allowsEmptyContent(self):
		return self.allow_empty

GRAMMAR.patterns["*"] = [
	AnyPattern(False)
]

GRAMMAR.patterns["**"] = [
	AnyPattern(True)
]

class WordPattern:
	def __repr__(self):
		return "WordPattern()"
	def toCode(self):
		return "<pattern that matches any single token>"
	def match(self, grammar, tokens, bits):
		if len(tokens) != 1 or not any(altbits >= bits for _, altbits in tokens[0].alternatives):
			return []
		return [[lambda: tokens[0], tokens[0].token]]
	def allowsEmptyContent(self):
		return False

GRAMMAR.patterns["."] = [
	WordPattern()
]

class StringContentPattern:
	def __repr__(self):
		return "StringContentPattern()"
	def toCode(self):
		return "<pattern that matches all strings without quote marks>"
	def match(self, grammar, tokens, bits):
		for token in tokens:
			if token.token == '"':
				return []
		string = ""
		subs = []
		current_subs = None
		for token in tokens:
			if current_subs is not None:
				if token.token == "]":
					string += " %s"
					alts = grammar.matchAll(current_subs, "EXPR-"+str(merkkijono.id), set())
					subs.append(alts)
					current_subs = None
				else:
					current_subs.append(token)
				continue
			if token.token == "[":
				current_subs = []
			elif token.token in [".", ":", ",", ";", "?", "!"]:
				string += token.token
			elif token.token == "%":
				string += " %%"
			else:
				string += " " + token.token
		string = string.strip()
		ans = []
		for alternative in itertools.product(*subs):
			ans.append([
				lambda: repr(string) + " % (" + ", ".join([p[0]() + '.extra["str"]' for p in alternative]) + ("," if len(alternative) == 1 else "") + ")",
				string % tuple([p[1] for p in alternative])
			])
		return ans
	def allowsEmptyContent(self):
		return True

GRAMMAR.patterns["STR-CONTENT"] = [
	StringContentPattern()
]

# Luokat

CLASSES = {}

def defineClass(name, superclass):
	name_str = tokensToString(name)
	name_code = nameToCode(name)
	
	if name_str in CLASSES:
		raise Exception("redefinition of class " + name_str)
	
	rclass = RClass(name_str, superclass, name)
	
	for clazz in reversed(superclass.superclasses()) if superclass else []:
		for fname in clazz.fields:
			rclass.fields[fname] = clazz.fields[fname].copy()
	
	pgl(".CLASS-PATTERN-%d ::= %s -> %s" % (rclass.id, name_code, name_str), FuncOutput(lambda: RPattern(rclass=rclass)))
	pgl(".CLASS-PATTERN ::= .CLASS-PATTERN-%d{$} -> $1" % (rclass.id,), identity)
	pgl(".CLASS-PATTERN ::= .CLASS-PATTERN-WITH-ADV-%d{$} -> $1" % (rclass.id,), identity)
	for clazz in rclass.superclasses():
		pgl(".CLASS-%d ::= %s -> %s" % (clazz.id, name_code, name_str), FuncOutput(lambda: rclass))
		pgl(".PATTERN-%d ::= %s -> %s" % (clazz.id, name_code, name_str), FuncOutput(lambda: RPattern(rclass=rclass)))
		if clazz is not rclass:
			for _, group_strs, group_codes in clazz.bit_groups:
				for group_str, group_code in zip(group_strs, group_codes):
					addBitPatternPhrase(rclass, rclass, group_str, group_code, group_strs)
					addBitClassPatternPhrase(rclass, group_str, group_code, group_strs)
			for attributePhraseAdder in clazz.attributePhraseAdders:
				attributePhraseAdder(rclass, rclass)
	pgl(".CLASS ::= %s -> %s" % (name_code, name_str), FuncOutput(lambda: rclass))
	
	def addMapFieldDefPattern(key_case, is_pre):
		pgl(".MAP-FIELD-DEF ::= Kutakin %s kohden .CLASS{ulkoolento} voi olla %s se{%s} %s %s kutsuttu .CLASS{nimento} . -> $1.$2 : {$4}" % (
			nameToCode(name, bits={"osanto", "yksikkö"}),
			".**" if is_pre else "",
			key_case,
			nameToCode(name, bits={key_case, "yksikkö"}),
			".**" if not is_pre else ""
		), FuncOutput(lambda *p: defineMapField(rclass, key_case, is_pre, *p, case="tulento")))
	
	for key_case in CASES:
		for is_pre in [True, False]:
			addMapFieldDefPattern(key_case, is_pre)
	
	return rclass

pgl(".CLASS-DEF ::= .* on käsite . -> class $1 : asia", FuncOutput(lambda x: defineClass(x, asia)))
pgl(".CLASS-DEF ::= .* on .CLASS{omanto} alakäsite . -> class $1 : $2", FuncOutput(defineClass))
pgl(".DEF ::= .CLASS-DEF -> $1", identity)

# Ominaisuudet

def definePolyparamField(field_id, owner, vtype, to_register, pattern, to_get, get_str_output, to_set, set_str_output, defa_pattern, to_set_defa, set_defa_str_output):
	
	for clazz in owner.subclasses():
		to_register(clazz)
	
	for clazz in vtype.superclasses():
		pgl(".EXPR-%d ::= .EXPR-%d{omanto} %s -> %s" % (clazz.id, owner.id, pattern({"$"}), get_str_output), FuncOutput(to_get))
	
	pgl(".FIELD-DEFAULT-DEF-%d ::= .CLASS-%d{omanto} %s on yleensä .EXPR-%d{nimento} . -> %s" % (
		field_id, owner.id, defa_pattern({"yksikkö", "nimento"}), vtype.id, set_defa_str_output
	), FuncOutput(to_set_defa))
	pgl(".DEF ::= .FIELD-DEFAULT-DEF-%d -> $1" % (field_id,), identity)
	
	pgl(".FIELD-VALUE-DEF-%d ::= .EXPR-%d{omanto} %s on .EXPR-%d{nimento} . -> %s" % (
		field_id, owner.id, pattern({"yksikkö", "nimento"}), vtype.id, set_str_output
	), FuncOutput(lambda *p: eval(to_set(*p))))
	pgl(".DEF ::= .FIELD-VALUE-DEF-%d -> $1" % (field_id,), identity)
	
	pgl(".CMD ::= .EXPR-%d{omanto} %s on nyt .EXPR-%d{nimento} . -> %s" % (
		owner.id, pattern({"yksikkö", "nimento"}), vtype.id, set_str_output
	), FuncOutput(to_set))
	
	pgl(".COND ::= .EXPR-%d{omanto} %s on .EXPR-%d{nimento} -> $1.%s==$2" % (
		owner.id, pattern({"yksikkö", "nimento"}), vtype.id, get_str_output
	), FuncOutput(lambda *p: (f'({to_get(*p[:-1])} == {p[-1]})', to_set(*p))))

def defineField(owner, name, vtype, case="nimento"):
	name_str = tokensToString(name, {"yksikkö", case})
	
	increaseCounter()
	counter = getCounter()
	
	pattern = lambda bits: nameToCode(name, bits, rbits={case, "yksikkö"})
	
	definePolyparamField(
		counter,
		owner,
		vtype,
		lambda clazz: clazz.addField(name_str, RField(counter, name_str, vtype)),
		pattern,
		lambda obj: f'{obj}.get({repr(name_str)})',
		"$1.%s" % (name_str,),
		lambda obj, val: f'{obj}.set({repr(name_str)}, {val})',
		"$1.%s = $2" % (name_str,),
		pattern,
		lambda clazz, defa: clazz.fields[name_str].setDefaultValue(eval(defa)),
		"$1.%s defaults $2" % (name_str,)
	)

pgl(".FIELD-DEF ::= .CLASS{ulkoolento} on .* , joka on .CLASS{nimento} . -> $1.$2 : $3", FuncOutput(defineField))
pgl(".FIELD-DEF ::= .CLASS{ulkoolento} on .* kutsuttu .CLASS{nimento} . -> $1.$2 : $3", FuncOutput(lambda *x: defineField(*x, case="tulento")))
pgl(".FIELD-DEF ::= .CLASS{ulkoolento} on .* kutsuttu joukko .CLASS{osanto,monikko} . -> $1.$2 : $3", FuncOutput(lambda *x: defineListField(*x, case="tulento")))
pgl(".DEF ::= .FIELD-DEF -> $1", identity)
pgl(".DEF ::= .MAP-FIELD-DEF -> $1", identity)

def defineMapField(key_class, key_case, is_pre, owner, name, vtype, case="nimento"):
	name_str = "m"+str(key_class.id)+"-"+tokensToString(name, rbits={case, "yksikkö"})
	name_code = nameToCode(name, rbits={case, "yksikkö"})
	
	increaseCounter()
	counter = getCounter()
	
	def createKeyPattern(category):
		return ".%s-%d{%s}" % (category, key_class.id, key_case)
	pre = lambda cat: (createKeyPattern(cat)+" " if not is_pre else "")
	post = lambda cat: (" "+createKeyPattern(cat) if is_pre else "")
	
	definePolyparamField(
		counter,
		owner,
		vtype,
		lambda clazz: clazz.addField(name_str, RField(counter, name_str, vtype, is_map=True)),
		lambda bits: pre("EXPR") + nameToCode(name, bits, rbits={case, "yksikkö"}) + post("EXPR"),
		lambda obj, key: f'{obj}.getMap({repr(name_str)}, {key})',
		"$1.%s" % (name_str,),
		lambda obj, key, val: f'{obj}.setMap({repr(name_str)}, {key}, {val})',
		"$1.%s[$2] = $3" % (name_str,),
		lambda bits: pre("CLASS") + nameToCode(name, bits, rbits={case, "yksikkö"}) + post("CLASS"),
		lambda clazz, _, defa: clazz.fields[name_str].setDefaultValue(eval(defa)),
		"$1.%s[$2] defaults $3" % (name_str,)
	)

def defineListField(owner, name, vtype, case="nimento"):
	name_str = "l-"+tokensToString(name, {"yksikkö", case})
	pattern = lambda bits: nameToCode(name, bits, rbits={case, "yksikkö"})
	
	increaseCounter()
	counter = getCounter()
	
	to_append = lambda val, obj: f'{obj}.appendSet({repr(name_str)}, {val})'
	to_remove = lambda val, obj: f'{obj}.removeSet({repr(name_str)}, {val})'
	
	pgl(".CMD ::= lisää .EXPR-%d{nimento} .EXPR-%d{omanto} %s . -> $2.%s.append($1)" % (
		vtype.id, owner.id, pattern({"yksikkö", "sisatulento"}), name_str
	), FuncOutput(to_append))
	
	pgl(".CMD ::= poista .EXPR-%d{nimento} .EXPR-%d{omanto} %s . -> $2.%s.append($1)" % (
		vtype.id, owner.id, pattern({"yksikkö", "sisaeronto"}), name_str
	), FuncOutput(to_remove))
	
	for named_code in ["", "( .* )"]:
		pgl(".CMD ::= toista jokaiselle .PATTERN-%d{ulkotulento} %s .EXPR-%d{omanto} %s : -> for each $1 in $2.%s:" % (
			vtype.id, named_code, owner.id, pattern({"yksikkö", "sisaolento"}), name_str
		), FuncOutput(lambda *p: ForParser(name_str, *p)))
	
	pgl(".COND ::= .EXPR-%d{omanto} %s sisältää .EXPR-%d{omanto} -> $1.%s.contains($2)" % (
		owner.id, pattern({"yksikkö", "nimento"}), vtype.id, name_str
	), FuncOutput(lambda obj, val: (f'({val} in {obj}.data[{repr(name_str)}])', to_append(val, obj))))
	
	pgl(".COND ::= .EXPR-%d{omanto} %s ei sisällä .EXPR-%d{osanto} -> !$1.%s.contains($2)" % (
		owner.id, pattern({"yksikkö", "nimento"}), vtype.id, name_str
	), FuncOutput(lambda obj, val: (f'({val} not in {obj}.data[{repr(name_str)}])', to_remove(val, obj))))

# Adjektiivit

def addBitPatternPhrase(owner, clazz, name_code, name_str, name_strs):
	pgl(".PATTERN-%d ::= %s .PATTERN-%d{$} -> %s($1)" % (clazz.id, name_code, owner.id, name_str),
		FuncOutput(lambda p: p.bitsOff(name_strs).bitOn(name_str)))

def addBitClassPatternPhrase(clazz, name_code, name_str, name_strs):
	pgl(".CLASS-PATTERN-%d ::= %s .CLASS-PATTERN-%d{$} -> %s($1)" % (clazz.id, name_code, clazz.id, name_str),
		FuncOutput(lambda p: p.bitsOff(name_strs).bitOn(name_str)))

def defineBit(owner, *names):
	increaseCounter()
	counter = getCounter()
	
	names = names
	name_strs = []
	name_codes = []
	for name in names:
		name_strs.append(tokensToString(name, {"yksikkö", "nimento"}))
		name_codes.append(nameToCode(name, rbits={"yksikkö", "nimento"}))
	owner.bit_groups.append((names, name_strs, name_codes))
	
	def addBitPhrases(name, name_str, name_code):
		name_code_nominative = nameToCode(name, bits={"yksikkö", "nimento"}, rbits={"yksikkö", "nimento"})
		
		pgl(".ENUM-DEFAULT-DEF-%d ::= .CLASS-%d{nimento} on yleensä %s . -> $1 defaults %s" % (
			counter, owner.id, name_code_nominative, name_str
		), FuncOutput(lambda c: c.bitOn(name_str)))

		for clazz in owner.subclasses():
			addBitPatternPhrase(clazz, clazz, name_code, name_str, name_strs)
			addBitClassPatternPhrase(clazz, name_code, name_str, name_strs)
		
		if owner.superclass:
			for clazz in owner.superclass.superclasses():
				addBitPatternPhrase(owner, clazz, name_code, name_str, name_strs)
		
		pgl(".CMD ::= .EXPR-%d{nimento} on nyt %s . -> $1.%s = True" % (
			owner.id, name_code_nominative, name_str
		), FuncOutput(lambda obj: f'obj.bitsOff({repr(name_strs)}).bitOn({repr(name_str)})'))
		
		pgl(".COND ::= .EXPR-%d{nimento} on %s -> $1.%s == True" % (
			owner.id, name_code_nominative, name_str
		), FuncOutput(lambda obj: (f'{repr(name_str)} in {obj}.bits', f'{obj}.bitsOff({repr(name_strs)}).bitOn({repr(name_str)})')))
		
	for name, name_str, name_code in zip(names, name_strs, name_codes):
		addBitPhrases(name, name_str, name_code)
	pgl(".DEF ::= .ENUM-DEFAULT-DEF-%d -> $1" % (counter,), identity)

pgl(".ENUM-DEF ::= .CLASS{nimento} voi olla .* . -> $1 has bit $2", FuncOutput(defineBit))
pgl(".ENUM-DEF ::= .CLASS{nimento} on joko .* tai .* . -> $1 has bits $2==!$3", FuncOutput(defineBit))
pgl(".ENUM-DEF ::= .CLASS{nimento} on joko .* , .* tai .* . -> $1 has bits $2==!($3|$4)", FuncOutput(defineBit))
pgl(".DEF ::= .ENUM-DEF -> $1", identity)

# Ehdot

pgl(".COND ::= .COND ja .COND -> $1 and $2", FuncOutput(lambda x, y: (f'({x[0]} and {y[0]})', f'({x[1]},{y[1]})')))
pgl(".COND ::= .COND , .COND ja .COND -> $1 and $2", FuncOutput(lambda x, y, z: (f'({x[0]} and {y[0]} and {z[0]})', f'({x[1]},{y[1]},{z[1]})')))

def defineCondition(grammar, is_adv, cases, nameds, first_named, owner, *args):
	args = list(args)
	cond_codes = args[-1]
	if first_named:
		first_name = args[0]
		del args[0]
	else:
		first_name = None
	pre = args[0]
	params = []
	i = 1
	j = 0
	while i < len(args)-1:
		if nameds[j]:
			params.append((args[i], args[i+2], args[i+1]))
		else:
			params.append((args[i], args[i+1], None))
		i += 3 if nameds[j] else 2
		j += 1
	
	tmp_vars = [f"_{i}" for i in range(len(params)+1)]
	
	grammar = grammar.copy()
	addParamPhrases(grammar, tmp_vars[0], owner, first_name)
	for case, (vtype, _, name), tmp_var in zip(cases, params, tmp_vars[1:]):
		addParamPhrases(grammar, tmp_var, vtype, name)
	
	# luodaan check- ja modify -koodit ja yhdistetään ne tupleiksi
	checks, modifys = [], []
	for cond_code in cond_codes:
		alts = grammar.matchAll(cond_code, "COND", set())
		if len(alts) != 1:
			sys.stderr.write("Monitulkintainen ehtolause: " + tokensToString(cond_code) + ". Vaihtoehdot: " + repr(alts) + "\n")
			return
		check, modify = alts[0][0]()
		checks.append(check)
		modifys.append(modify)
	
	check = "(" + ", ".join(checks) + ")"
	modify = "(" + ", ".join(modifys) + ")"
	
	name_str = " ".join([tokensToString(pre)] + [
		"- %s" % (tokensToString(post),) for _, post, _ in params
	])
	
	pattern = " ".join([tokensToCode(pre)] + [
		".EXPR-%d{%s} %s" % (vtype.id, case, tokensToCode(post)) for case, (vtype, post, _) in zip(cases, params)
	])
	
	make_tuple = lambda content, p: ", ".join([
		"pushStackFrame()",
	] + [f"putVar({repr(tmp_var)}, {a})" for tmp_var, a in zip(tmp_vars, p)] + [
		content,
		"popStackFrame()",
	])
	
	pgl(".COND ::= .EXPR-%d{nimento} on %s -> $1~%s" % (owner.id, pattern, name_str),
		FuncOutput(lambda *p: ("(" + make_tuple(check, p) + ")[-2]", "(" + make_tuple(modify, p) + ")")))
	
	# adjektiivisuus päätellään viimeisen sanan perusteella
	if len(pre) == 0 and (len(params) == 0 or len(params[-1][1]) == 0):
		is_adjective = False
	else:
		last_token = pre[-1] if len(params) == 0 else params[-1][1][-1]
		is_adjective = not is_adv and ("laatusana" in last_token.bits() or "nimisana_laatusana" in last_token.bits()) and "nimento" in last_token.bits()
	
	# adjektiivisen ja adverbiaalisen fraasin yhteinen funktio
	func = lambda *p: p[-1].addCondition(RCondition(
		"_obj", "(" + make_tuple(check, ("_obj",)+p[:-1]) + ")[-2]", "(" + make_tuple(modify, ("_obj",)+p[:-1]) + ")"
	))
	
	# yhteinen output-merkkijonon osa
	output_str = name_str + "(" + ", ".join([f"${n}" for n in range(len(params)+1)]) + ")"
	
	if is_adjective:
		def addAttributePhrase(owner, clazz):
			pgl(".PATTERN-%d ::= %s .PATTERN-%d{$} -> %s" % (clazz.id, pattern, owner.id, output_str), FuncOutput(func))
			if owner is clazz: # ehto tarvitaan, ettei tätä lisättäisi kahdesti (alempana kahdessa for-silmukassa)
				pgl(".CLASS-PATTERN-%d ::= %s .CLASS-PATTERN-%d{$} -> %s" % (clazz.id, pattern, clazz.id, output_str), FuncOutput(func))
	else:
		def addAttributePhrase(owner, clazz):
			pgl(".PATTERN-%d ::= %s oleva{$} .PATTERN-%d{$} -> %s" % (clazz.id, pattern, clazz.id, output_str), FuncOutput(func))
			if owner is clazz:
				pgl(".CLASS-PATTERN-%d ::= %s oleva{$} .CLASS-PATTERN-%d{$} -> %s" % (clazz.id, pattern, clazz.id, output_str), FuncOutput(func))
				pgl(".CLASS-PATTERN-WITH-ADV-%d ::= .CLASS-PATTERN-%d %s -> %s" % (clazz.id, clazz.id, pattern, output_str),
					FuncOutput(lambda *p: p[0].addCondition(RCondition(
						"_obj", "(" + make_tuple(check, ("_obj",)+p[1:]) + ")[-2]", "(" + make_tuple(modify, ("_obj",)+p[1:]) + ")"
					))))
	
	if owner.superclass:
		for clazz in owner.superclass.superclasses():
			addAttributePhrase(owner, clazz)
	
	for clazz in owner.subclasses():
		addAttributePhrase(clazz, clazz)
	
	owner.attributePhraseAdders.append(addAttributePhrase)

class ConditionParser:
	def __init__(self, *p):
		self.args = p
	def parse(self, file, grammar):
		lines = []
		while True:
			line = file.readline()
			if not line.strip():
				break
			lines.append(tokenize(line))
		return defineCondition(grammar, *self.args, lines)

def addConditionDefPatterns(cases):
	for first_named, *nameds in itertools.product(*[[False, True]]*(len(cases)+1)):
		addConditionDefPattern(cases, first_named, nameds)

def addConditionDefPattern(cases, first_named, nameds):
	fname = "" if not first_named else "( .* )"
	pattern = " ".join(["[ .CLASS{%s} %s ] .**" % (case, "" if not named else "( .* )") for case, named in zip(cases,nameds)])
	pgl(".COND-DEF ::= Määritelmä . Kun .CLASS{nimento} %s on \" .** %s \" : -> def $1~ $*:" % (fname, pattern),
		FuncOutput(lambda *p: ConditionParser(False, cases, nameds, first_named, *p)))

for i in [0,1,2]:
	for cases in itertools.product(*[CASES]*i):
		addConditionDefPatterns(cases)

pgl(".DEF ::= .COND-DEF -> $1", identity)

# Muuttujat

def defineVariable(name, class_pattern):
	name_str = tokensToString(name)
	pattern = lambda bits: nameToCode(name, bits, rbits={"yksikkö", "nimento"})
	
	vtype = class_pattern.type()
	GLOBAL_SCOPE.variables[name_str] = class_pattern.newInstance(name)
	
	to_get = lambda: f'getVar({repr(name_str)})'
	to_set = lambda x: f'setVar({repr(name_str)}, {x})'
	
	for clazz in vtype.superclasses():
		pgl(".EXPR-%d ::= %s -> %s" % (clazz.id, pattern({"$"}), name_str),
			FuncOutput(to_get))
	
	pgl(".CMD ::= %s on nyt EXPR-%d{nimento} . -> %s = $1" % (pattern({"yksikkö", "nimento"}), vtype.id, name_str),
		FuncOutput(to_set))
	
	pgl(".COND ::= %s on .EXPR-%d{nimento} -> %s==$2" % (
		pattern({"yksikkö", "nimento"}), vtype.id, name_str
	), FuncOutput(lambda x: (f'{to_get()}.equals({x})', to_set(x))))

pgl(".VARIABLE-DEF ::= .* on .CLASS-PATTERN{nimento} . -> $1 : $2", FuncOutput(defineVariable))
pgl(".DEF ::= .VARIABLE-DEF -> $1", identity)

# Apufunktio

def addParamPhrases(grammar, case, vtype, name):
	if name:
		for clazz in vtype.superclasses():
			grammar.parseGrammarLine(".EXPR-%d ::= %s -> %s param" % (
				clazz.id, nameToCode(name, rbits={"yksikkö", "nimento"}), vtype.name
			), FuncOutput(lambda: f'getVar({repr(case)})'))
	else:
		pronoun = "hän" if "inhimillinen" in vtype.bits else "se"
		for clazz in vtype.superclasses():
			grammar.parseGrammarLine(".EXPR-%d ::= %s{$} -> %s param" % (clazz.id, pronoun, vtype.name),
				FuncOutput(lambda: f'getVar({repr(case)})'))

# Toiminnot

class ListenerParser:
	def __init__(self, args):
		self.args = args
		self.params = self.args[1]
	def parse(self, file, grammar):
		grammar = grammar.copy()
		for i, (c, p, n) in enumerate(self.params):
			addParamPhrases(grammar, f"_{i}", p.type(), n)
		grammar.parseGrammarLine(".CMD ::= keskeytä toiminto . -> stop", FuncOutput(lambda: 'SCOPE[-1].bitOn("stop action")')) # suoritetaan isäntäscopessa
		body = parseBlock(file, grammar)
		return RListener(*self.args, body)

def defineAction(name, params, pre, post):
	action = RAction(name)
	
	def defineActionListener(patterns, priority, is_special_case, is_general_case):
		return ListenerParser((action, [(a_case, pattern, name) for (pattern, name), (_, _, a_case) in zip(patterns, params)], priority, is_special_case, is_general_case))
	
	def separateGroups(groups, nameds):
		i = 0
		j = 0
		ans = []
		while i < len(groups):
			if nameds[j]:
				ans.append((groups[i], groups[i+1]))
				i += 2
			else:
				ans.append((groups[i], None))
				i += 1
			j += 1
		return ans
	
	def addListenerDefPattern(p_pre, p_case, p_post, priority, is_special_case, is_general_case, nameds):
		pgl(".LISTENER-DEF-%d ::= %s %s %s %s{-minen,%s} %s %s : -> def %s($1):" % (
			action.id,
			p_pre,
			" ".join([
				"%s .PATTERN-%d{%s,yksikkö}" % (tokensToCode(a_pre), a_class.id, a_case)
				+ (" ( .* )" if named else "")
			for named, (a_pre, a_class, a_case) in zip(nameds, params)]),
			tokensToCode(pre), name.baseform("-minen"), p_case, tokensToCode(post), p_post,
			name.token
		), FuncOutput(lambda *groups: defineActionListener(separateGroups(groups, nameds), priority, is_special_case, is_general_case)))
	
	for p_pre, p_case, p_post, priority, is_special_case, is_general_case in LISTENER_PRIORITIES:
		for nameds in itertools.product(*[[False, True]]*len(params)):
			addListenerDefPattern(p_pre, p_case, p_post, priority, is_special_case, is_general_case, nameds)
	pgl(".DEF ::= .LISTENER-DEF-%d -> $1" % (action.id,), identity)
	
	def defineCommand(category, cmd_cases, pre, *posts):
		command_pattern = "%s %s" % (
			tokensToCode(pre),
			" ".join([
				".EXPR-%d{%s,yksikkö} %s" % (a_class.id, cmd_case, tokensToCode(post))
			for cmd_case, (_, a_class, _), post in zip(cmd_cases, params, posts)])
		)
		pgl(".%s ::= %s . -> %s($1)" % (
			category,
			command_pattern,
			name.token
		), FuncOutput(lambda *val: f'ACTIONS[{repr(action.id)}].run([{", ".join(val)}])'))
		if category == "PLAYER-CMD":
			action.addPlayerCommand(command_pattern)
	
	def addCommandDefPhrase(cmd_cases):
		cmd_pattern = " ".join([
				"[ " + a_class.nameToCode({cmd_case, "yksikkö"}) + " ] .**"
			for cmd_case, (_, a_class, _) in zip(cmd_cases, params)])
		action_patterns = [
			"%s %s{-minen,CASE} %s" % (
				tokensToCode(pre), name.baseform("-minen"), tokensToCode(post),
			)
		]
		if len(params) != 0:
			action_patterns.append(
				"%s %s %s{-minen,CASE} %s" % (
					" ".join([
						tokensToCode(a_pre) + a_class.nameToCode({a_case, "yksikkö"})
					for a_pre, a_class, a_case in params]),
					tokensToCode(pre), name.baseform("-minen"), tokensToCode(post)
				)
			)
			if sum([len(a_pre) for a_pre, _, _ in params]) + len(pre) + len(post) != 0:
				action_patterns.append(
					"%s %s %s{-minen,CASE} %s" % (
						" ".join([tokensToCode(a_pre) for a_pre, _, _ in params]),
						tokensToCode(pre), name.baseform("-minen"), tokensToCode(post),
					)
				)
		for action_pattern in action_patterns:
			pgl(".COMMAND-DEF-%d ::= %s komento on \" .** %s \" . -> def %s command" % (
				action.id,
				action_pattern.replace("CASE", "omanto"),
				cmd_pattern,
				name.token
			), FuncOutput(lambda *p: defineCommand("CMD", cmd_cases, *p)))
			pgl(".COMMAND-DEF-%d ::= tulkitse \" .** %s \" %s . -> def %s command" % (
				action.id,
				cmd_pattern,
				action_pattern.replace("CASE", "olento"),
				name.token
			), FuncOutput(lambda *p: defineCommand("PLAYER-CMD", cmd_cases, *p)))
	
	for cmd_cases in itertools.product(*[CASES]*len(params)):
		addCommandDefPhrase(cmd_cases)
	
	pgl(".DEF ::= .COMMAND-DEF-%d -> $1" % (action.id,), identity)

def addActionDefPattern(cases):
	def transformArgs(args):
		ans = []
		i = -2
		for case, i in zip(cases, range(0, len(cases)*2, 2)):
			ans.append((args[i], args[i+1], case))
		return args[i+3], ans, args[i+2], args[i+4]
	pgl(".ACTION-DEF ::= %s .** ..{-minen,nimento} .** on toiminto . -> action $%d(%d)" % (
		" ".join([".** [ .CLASS{%s,yksikkö} ]" % (case,) for case in cases]),
		len(cases)*2+2,
		len(cases)
	), FuncOutput(lambda *p: defineAction(*transformArgs(p))))

for i in [0,1,2]:
	for cases in itertools.product(*[CASES]*i):
		addActionDefPattern(cases)

pgl(".DEF ::= .ACTION-DEF -> $1", identity)

# Sisäänrakennetut luokat

asia = defineClass(tokenize("asia"), None)

merkkijono = defineClass(tokenize("merkkijono"), asia)
pgl('.EXPR-%d ::= " .STR-CONTENT " -> "$1"' % (asia.id,), FuncOutput(lambda s: f'createStringObj({s})'))
pgl('.EXPR-%d ::= " .STR-CONTENT " -> "$1"' % (merkkijono.id,), FuncOutput(lambda s: f'createStringObj({s})'))
pgl('.EXPR-%d ::= rivinvaihto{$} -> "\\n"' % (merkkijono.id,), FuncOutput(lambda: 'createStringObj("\\n")'))
pgl('.EXPR-%d ::= .EXPR-%d{$} isolla alkukirjaimella -> capitalize($1)' % (merkkijono.id, merkkijono.id),
	FuncOutput(lambda x: f'createStringObj({x}.extra["str"].capitalize())'))

# For-silmikka

class ForParser:
	def __init__(self, field_name, *args):
		self.field_name = field_name
		self.args = args
	def parse(self, file, grammar):
		grammar = grammar.copy()
		
		param_pattern = self.args[0]
		param_name = None if len(self.args) == 2 else self.args[1]
		obj = self.args[-1]
		
		addParamPhrases(grammar, "_val", param_pattern.type(), param_name)
		
		block = parseBlock(file, grammar)
		block_str = "lambda: (" + ", ".join(block) + ")"
		
		return '%s.forSet(%s, %s, %s, %s)' % (obj, repr(self.field_name), repr("_val"), param_pattern.toPython(), block_str)

# Tulostaminen

pgl(".CMD ::= sano .EXPR-%d{nimento} . -> print($1)" % (asia.id,), FuncOutput(lambda x: f'say({x}.asString())'))

# Komentojen jäsentäminen

def parseBlock(file, grammar):
	ans = []
	while True:
		line = file.readline()
		if not line.strip():
			break
		alternatives = grammar.matchAll(tokenize(line.strip()), "CMD", set())
		if len(alternatives) != 1:
			sys.stderr.write("Virhe jäsennettäessä riviä `" + line.strip() + "'. Vaihtoehdot: " + ", ".join([a[1] for a in alternatives]) + "\n")
			break
		if alternatives[0][1][-1] == ":":
			ans.append(alternatives[0][0]().parse(file, grammar))
		else:
			ans.append(alternatives[0][0]())
	return ans

# Tiedoston lataaminen

def loadFile(file):
	while True:
		line = file.readline()
		if not line:
			break
		if not line.strip() or line[0] == ">":
			continue
		a = GRAMMAR.matchAll(tokenize(line.strip()), "DEF", set())
		if len(a) == 1:
			t = a[0][0]()
			if a[0][1][-1] == ":":
				t.parse(file, GRAMMAR)
		else:
			print("Virhe jäsennettäessä tiedoston riviä `" + line.strip() + "'.")
# Standardikirjasto

def loadStandardLibrary():
	my_path = os.path.dirname(os.path.realpath(__file__))
	with open(os.path.join(my_path, "std.txt")) as f:
		loadFile(f)

# Kääntäminen

def compileAll(file=sys.stdout):
	compiled_classes = [cl.toPython() for cl in CLASSES_IN_ORDER]
	compiled_objects = [ob.toPython() for ob in getObjects()]
	print("from suomilog.patternparser import Grammar, Token", file=file)
	print("from retki.language import *", file=file)
	print("OBJECTS = {}", file=file)
	print("GRAMMAR = Grammar()", file=file)
	for decl, _ in compiled_classes+compiled_objects:
		if decl:
			print(decl, file=file)
	for _, code in compiled_classes+compiled_objects:
		if code:
			print(code, file=file)
	for key in GLOBAL_SCOPE.variables:
		obj = GLOBAL_SCOPE.variables[key]
		print(f'GLOBAL_SCOPE.variables[{repr(key)}] = OBJECTS[{repr(obj.id)}]', file=file)
	for key in ACTIONS:
		print(ACTIONS[key].toPython(), file=file)
	for listener in ACTION_LISTENERS:
		print(listener.toPython(), file=file)
	print("playGame(GRAMMAR)", file=file)

# Pääohjelma

def compileFile(infile, outfile):
	saveObjects()
	loadStandardLibrary()
	loadFile(infile)
	compileAll(outfile)

def interactive():
	saveObjects()
	loadStandardLibrary()

	def complete_file(t, s):
		path, file = os.path.split(t)
		alternatives = []
		try:
			for c in sorted(["/kielioppi", "/käsitteet", "/debug ", "/virheet", "/match ", "/eval ", "/lataa ", "/käännä", "/pelitila", "/komentotila", "/määrittelytila"]):
				if c.startswith(t):
					alternatives.append(c)
			for f in filter(lambda f: f.startswith(file), os.listdir(path or ".")):
				alt = os.path.join(path, f)
				if os.path.isdir(alt):
					alternatives.append(os.path.join(alt, ""))
				else:
					alternatives.append(alt)
			return alternatives[s] if s < len(alternatives) else None
		except Exception as e:
			print(e)
	readline.set_completer(complete_file)
	readline.set_completer_delims(" ")
	readline.parse_and_bind('tab: complete')
	
	def printStatistics():
		n_patterns = sum([len(category) for category in GRAMMAR.patterns.values()])
		print("Ladattu", n_patterns, "fraasia.")
	
	mode = ["DEF", "CMD", "PLAYER-CMD"]
	mode_chars = ["!", "?"]
	
	printStatistics()
	while True:
		try:
			line = input(">> ")
		except EOFError:
			break
		if not line:
			continue
		if line == "/kielioppi":
			GRAMMAR.print()
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
		elif line == "/virheet":
			errors = ERROR_STACK[-1]
			if len(errors) > 0:
				print("Mahdollisia virheitä:")
				for error in errors:
					print(error+"\n")
			else:
				print("Ei virheitä.")
			continue
		elif line.startswith("/match"):
			args = line[6:].strip()
			cat = args[:args.index(" ")]
			expr = args[args.index(" ")+1:]
			print(f"Matching `{expr}' ~ .{cat}")
			ints = GRAMMAR.matchAll(tokenize(expr), cat, set())
			for _, string in ints:
				print(string)
			continue
		elif line.startswith("/eval"):
			print(eval(line[5:].strip()))
			continue
		elif line.startswith("/lataa"):
			try:
				with open(line[6:].strip()) as f:
					loadFile(f)
			except:
				traceback.print_exc()
			printStatistics()
			continue
		elif line == "/käännä":
			compileAll()
			continue
		elif line.startswith("/pelitila"):
			mode = ["PLAYER-CMD", "CMD", "DEF"]
			continue
		elif line.startswith("/komentotila"):
			mode = ["CMD", "DEF", "PLAYER-CMD"]
			continue
		elif line.startswith("/määrittelytila"):
			mode = ["DEF", "CMD", "PLAYER-CMD"]
			continue
		del ERROR_STACK[:]
		ERROR_STACK.append([])
		phrase_type = mode[0]
		if line[0] in mode_chars:
			phrase_type = mode[mode_chars.index(line[0])+1]
			line = line[1:]
		silent = mode[0] == phrase_type == "PLAYER-CMD"
		interpretations = GRAMMAR.matchAll(tokenize(line), phrase_type, set())
		if len(interpretations) == 0:
			print("Ei tulkintaa.")
		elif len(interpretations) == 1:
			if not silent:
				print(interpretations[0][1])
			try:
				string = interpretations[0][0]()
				if not silent:
					print(string)
				if string:
					eval(string)
			except:
				traceback.print_exc()
		else:
			print("Löydetty", len(interpretations), "tulkintaa:")
			for _, interpretation in interpretations:
				print(interpretation)
		if not mode[0] == phrase_type == "PLAYER-CMD":
			printStatistics()

def main():
	parser = argparse.ArgumentParser(description='Finnish Interactive Fiction language inspired by Inform 7')
	parser.add_argument('input', type=argparse.FileType('r'), nargs='?', help='source code file')
	parser.add_argument('--output', "-o", type=argparse.FileType('w'), nargs='?', help='target code file')
	
	args = parser.parse_args()
	
	output = args.output or sys.stdout
	
	if args.input:
		compileFile(args.input, output)
	else:
		interactive()
