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
    "1.9.0" = {
      pypiSha256 = "1p4y4qd1ndzi1lg4fhnvq1rqz7611yrwnwwvzh63aazfpzaplyd8";
      sourceSha256 = "1g6khxc7mvm3q8rqksw9dwn4l2w8wzvr3zb74n2lb7g5ilpxsadd";
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
