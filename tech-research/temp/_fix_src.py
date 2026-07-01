import pathlib, re
p = pathlib.Path(r"D:\013148\code\AI技术趋势雷达\验证\API接口清单与验证方案.md")
c = p.read_text(encoding="utf-8")
lines = c.split(chr(10))
s = None
for i, ln in enumerate(lines):
    if chr(34)+chr(115)+chr(111)+chr(117)+chr(114)+chr(99)+chr(101)+chr(95)+chr(115)+chr(99)+chr(111)+chr(112)+chr(101)+chr(34) in ln and chr(97)+chr(119)+chr(115)+chr(45)+chr(109)+chr(108)+chr(45)+chr(98)+chr(108)+chr(111)+chr(103) in ln:
        s = i; break
if s is None:
    print(chr(70)+chr(65)+chr(73)+chr(76)); exit(1)
nl = lines[:s] + lines[s+1:]
nl[s] = chr(32)*4 + chr(34)+chr(115)+chr(111)+chr(117)+chr(114)+chr(99)+chr(101)+chr(95)+chr(115)+chr(99)+chr(111)+chr(112)+chr(101)+chr(34) + chr(58) + chr(32) + chr(91)+chr(34)+chr(120)+chr(105)+chr(110)+chr(45)+chr(122)+chr(104)+chr(105)+chr(45)+chr(121)+chr(117)+chr(97)+chr(110)+chr(34)+chr(44)+chr(32)+chr(34)+chr(108)+chr(105)+chr(97)+chr(110)+chr(103)+chr(122)+chr(105)+chr(119)+chr(101)+chr(105)+chr(34)+chr(44)+chr(32)+chr(34)+chr(97)+chr(114)+chr(120)+chr(105)+chr(118)+chr(45)+chr(99)+chr(115)+chr(45)+chr(97)+chr(105)+chr(34)+chr(93)
p.write_text(chr(10).join(nl), encoding="utf-8")
print(chr(68)+chr(79)+chr(78)+chr(69))
