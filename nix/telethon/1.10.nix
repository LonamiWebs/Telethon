{ lib, buildPythonPackage, pythonOlder
, fetchFromGitHub ? null, fetchPypi ? null, fetchpatch ? null
, pyaes, rsa
, version
, useRelease ? true
}:

assert useRelease -> fetchPypi != null;
assert !useRelease -> fetchFromGitHub != null;
let
  common = import ./common.nix {
    inherit lib fetchFromGitHub fetchPypi fetchpatch;
  };
  versions = {
    "1.10.1" = {
      pypiSha256 = "1ql8ai01c6v3l13lh3csh37jjkrb33gj50jyvdfi3qjn60qs2rfl";
      sourceSha256 = "1skckq4lai51p476r3shgld89x5yg5snrcrzjfxxxai00lm65cbv";
    };
    "1.10.0" = {
      pypiSha256 = "1n2g2r5w44nlhn229r8kamhwjxggv16gl3jxq25bpg5y4qgrxzd8";
      sourceSha256 = "1rvrc63j6i7yr887g2csciv4zyy407yhdn4n8q2q00dkildh64qw";
    };
  };
in buildPythonPackage rec {
  pname = "telethon";
  inherit version;

  src = common.fetchTelethon {
    inherit useRelease version;
    versionData = versions.${version};
  };

  propagatedBuildInputs = [ rsa pyaes ];

  doCheck = false; # No tests available

  disabled = pythonOlder "3.5";
  meta = common.meta;
}
