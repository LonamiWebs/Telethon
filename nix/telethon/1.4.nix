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
    "1.4.3" = {
      pypiSha256 = "1igslvhd743qy9p4kfs7lg09s8d5vhn9jhzngpv12797569p4lcj";
      sourceSha256 = "19vz0ppk7lq1dmqzf47n6h023i08pqvcwnixvm28vrijykq0z315";
    };
    "1.4.2" = {
      pypiSha256 = "1f4ncyfzqj4b6zib0417r01pgnd0hb1p4aiinhlkxkmk7vy5fqfy";
      sourceSha256 = "0rsbz5kqp0d10gasadir3mgalc9aqq4fcv8xa1p7fg263f43rjl4";
    };
    "1.4.1" = {
      pypiSha256 = "1n0jhdqflinyamzy5krnww7hc0s7pw9yfck1p7816pdbgir74qsw";
      sourceSha256 = "07q48gw4ry3wf9yzi6kf8lw3b23a0dvk9r8sabpxwrlqy7gnksxx";
    };
    "1.4.0" = {
      version = "1.4";
      pypiSha256 = "1g7rznwmj87n9k86zby9i75h570hm84izrv0srhsmxi52pjan1ml";
      sourceSha256 = "14nv86yrj01wmlj5cfg6iq5w03ssl67av1arfy9mq1935mly5nly";
    };
  };
in buildPythonPackage rec {
  pname = "telethon";
  inherit version;

  src = common.fetchTelethon {
    inherit useRelease version;
    versionData = versions.${version};
  };
  patches = lib.optionals (!useRelease) [
    (if (lib.versionOlder version "1.4.3") then
      common.patches.generator-use-pathlib-to-1_4_3
    else
      common.patches.generator-use-pathlib-from-1_4_3-to-1_5_0)
    common.patches.generator-use-pathlib-open-to-1_5_3
    common.patches.sort-generated-tlobjects-to-1_7_1
  ];

  propagatedBuildInputs = [ async_generator rsa pyaes ];

  doCheck = false; # No tests available

  disabled = pythonOlder "3.5";
  meta = common.meta;
}
