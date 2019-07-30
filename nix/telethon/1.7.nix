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
    "1.7.7" = {
      pypiSha256 = "0mgpihjc7g4gfrq57srripdavxbsgivn4qsjanv3yds5drskciv0";
      sourceSha256 = "08c3iakd7fyacc79pg8hyzpa6zx3gbp7xivi10af34zj775lp2pi";
    };
    "1.7.6" = {
      pypiSha256 = "192xda98685s3hmz7ircxpsn7yq913y0r1kmqrsav90m4g4djn4j";
      sourceSha256 = "1ss2pfpd3hby25g9ighbr7ccp66awfzda4srsnvr9s6i28har6ag";
    };
    "1.7.5" = {
      pypiSha256 = "0i5s7ahicw5k0s1i7pi26vc6rp6ppr1gr848sa61yh3qqa4c0qnr";
      sourceSha256 = "1rssh0l466h9y6v0z095c9aa63nz9im7gg5771jjj5w70mkpm5w6";
    };
    "1.7.4" = {
      pypiSha256 = "1qpc9f1y559zdwz59qqz4hbf1mrynjjbcg357nzaa2x5a2q4lz0s";
      sourceSha256 = "1q43lwfp67q4skfcrb6sdlnjw4ajrpizf08fd9wjrw521kkd8g4y";
    };
    "1.7.3" = {
      pypiSha256 = "0s8qmsarlfgpb0k3w50siv354hpa7b1dnrjjd0iqz7vc5bc7ni84";
      sourceSha256 = "0c393smp1qm8kk39r0k31p74p89qzvjdjxq4bxq75h07a1yqbs8x";
    };
    "1.7.2" = {
      pypiSha256 = "0465dwikhpbka2sj1g952rac03jkixq497gbmmyx2i9xb594db27";
      sourceSha256 = "1gw09zbaqvn074skwjhmm4yp8p75rw9njwjbkcfvqb4gr6dg8wpq";
    };
    "1.7.1" = {
      pypiSha256 = "186z6imf7zqy8vf4yv2w2kxpd7lxmfppa1qi8nxjdgq8rz7wbglf";
      sourceSha256 = "05mpqfj4w5qxyl1ai5p0f31pkagz55xxh8060r8y9i3d44j9bn1c";
    };
    "1.7.0" = {
      version = "1.7";
      pypiSha256 = "06cqb121k2y0h3x7gvckyvbsn97wc1a25pghinxz2vb7vg8wwxvw";
      sourceSha256 = "0myx32hqax71ijfw6ksxvk27cb6x06kbz8jb7ib9d1cayr2viir6";
    };
  };
in buildPythonPackage rec {
  pname = "telethon";
  inherit version;

  src = common.fetchTelethon {
    inherit useRelease version;
    versionData = versions.${version};
  };
  patches = lib.optional (!useRelease && lib.versionOlder version "1.7.1")
    common.patches.sort-generated-tlobjects-to-1_7_1;

  propagatedBuildInputs = [ rsa pyaes ];

  doCheck = false; # No tests available

  disabled = pythonOlder "3.5";
  meta = common.meta;
}
