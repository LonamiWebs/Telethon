{ lib, buildPythonPackage, pythonOlder
, fetchFromGitHub ? null, fetchPypi ? null, fetchpatch ? null
, async_generator, pyaes, rsa
, version
, useRelease ? true
}:

assert useRelease -> fetchPypi != null;
assert !useRelease -> fetchFromGitHub != null && fetchpatch != null;
let
  common = import ./common.nix {
    inherit lib fetchFromGitHub fetchPypi fetchpatch;
  };
  versions = {
    "1.5.5" = {
      pypiSha256 = "1qpc4vc3lidhlp1c7521nxizjr6y5c3l9x41knqv02x8n3l9knxa";
      sourceSha256 = "1x5niscjbrg5a0cg261z6awln57v3nn8si5j58vhsnckws2c48a5";
    };
    "1.5.4" = {
      pypiSha256 = "1kjqi3wy4hswsf3vmrjg7z5c3f9wpdfk4wz1yfsqmj9ppwllkjsj";
      sourceSha256 = "0rmp9zk7a354nb39c01mjcrhi2j6v9im40xmdcvmizx990vlv476";
    };
    "1.5.3" = {
      pypiSha256 = "11xd5ni0chzsfny0vwwqyh37mvmrwrk2bmkhwp1ipbxyis8jjjia";
      sourceSha256 = "1l3i6wx3fgcy3vmr75qdbv5fvc5qnk0j47hv7jszsqq9rvqvz2xs";
    };
    "1.5.2" = {
      pypiSha256 = "0ymv6l9xn41sgpkilqkivwbjna89m43i0a728lak2cppp7i1i1h7";
      sourceSha256 = "0gnqvlhh3qyvibl7icn6774rshlx1nnhb5f78609da44743lyv17";
    };
    "1.5.1" = {
      pypiSha256 = "1ypxpsfj814gzln4fl7z17l1l6q0bzd5p1ivas85yim3a992ixww";
      sourceSha256 = "15w5nshvmj8hgqdcbpw0fjcf1cspaci8dldm9ml1pmijw7zgmpdg";
    };
    "1.5.0" = {
      version = "1.5";
      pypiSha256 = "1kzkzcxyz7adjzvm2ml9faz2c5yx469j211yvi5xfvjwp58ic2jc";
      sourceSha256 = "12232d3xfv0bbykk9xaxpxsr3656ywjx4ra1q5q99rpp6wv438n1";
    };
  };
in buildPythonPackage rec {
  pname = "telethon";
  inherit version;

  src = common.fetchTelethon {
    inherit useRelease version;
    versionData = versions.${version};
  };
  patches = lib.optionals (!useRelease) ([
    common.patches.sort-generated-tlobjects-to-1_7_1
  ] ++ lib.optional (lib.versionOlder version "1.5.3")
      common.patches.generator-use-pathlib-open-to-1_5_3);

  propagatedBuildInputs = [ async_generator rsa pyaes ];

  doCheck = false; # No tests available

  disabled = pythonOlder "3.5";
  meta = common.meta;
}
