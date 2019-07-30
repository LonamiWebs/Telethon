{ lib, buildPythonPackage, pythonOlder
, fetchFromGitHub ? null, fetchPypi ? null, fetchpatch ? null
, pyaes, rsa
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
    "1.6.2" = {
      pypiSha256 = "074h5gj0c330rb1nxzpqm31fp1vw7calh1cdkapbjx90j769iz18";
      sourceSha256 = "1daqlb4sva5qkljzbjr8xvjfgp7bdcrl2li1i4434za6a0isgd3j";
    };
    "1.6.1" = {
      # hotpatch with missing .pyc files and fixed Telethon.egg-info perms
      pypiVersion = "1.6.1.post1";
      pypiSha256 = "17s1qp69bbj6jniam9wbcpaj60ah56sjw0q3kr8ca28y17s88si7";
      # pypiVersion = "1.6.1";
      # pypiSha256 = "036lhr1jr79np74c6ih51c4pjy828r3lvwcq07q5wynyjprm1qbz";
      sourceSha256 = "1hk1bpnk51rpsifb67s31c2qph5hmw28i2vgh97i4i56vynx2yxz";
    };
    "1.6.0" = {
      version = "1.6";
      pypiSha256 = "06prmld9068zcm9rfmq3rpq1szw72c6dkxl62b035i9w8wdpvg0m";
      sourceSha256 = "0qk14mrnvv9a043ik0y2w6q97l83abvbvn441zn2jl00w4ykfqrh";
    };
  };
in buildPythonPackage rec {
  pname = "telethon";
  inherit version;

  src = common.fetchTelethon {
    inherit useRelease version;
    versionData = versions.${version};
  };
  patches = lib.optional (!useRelease)
    common.patches.sort-generated-tlobjects-to-1_7_1;

  propagatedBuildInputs = [ rsa pyaes ];

  doCheck = false; # No tests available

  disabled = pythonOlder "3.5";
  meta = common.meta;
}
