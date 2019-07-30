{ lib, fetchFromGitHub ? null, fetchPypi ? null, fetchpatch ? null }:

rec {
  fetchTelethon = { useRelease, version, versionData }:
    if useRelease then assert versionData.pypiSha256 != null; fetchPypi {
      pname = "Telethon";
      version = versionData.pypiVersion or (versionData.version or version);
      sha256 = versionData.pypiSha256;
    } else assert versionData.sourceSha256 != null; fetchFromGitHub {
      owner = "LonamiWebs";
      repo = "Telethon";
      rev = versionData.rev or "v${versionData.version or version}";
      sha256 = versionData.sourceSha256;
    };

  fetchpatchTelethon = { rev, ... } @ args:
    fetchpatch ({
      url = "https://github.com/LonamiWebs/Telethon/commit/${rev}.patch";
    } // (builtins.removeAttrs args [ "rev" ]));

  # sorted by name, then by logical version range
  patches = rec {
    generator-use-pathlib-to-1_4_3 = ./generator-use-pathlib-to-1_4_3.patch;
    generator-use-pathlib-from-1_4_3-to-1_5_0 = [
      (fetchpatchTelethon {
        rev = "e71c556ca71aec11166dc66f949a05e700aeb24f";
        sha256 = "058phfaggf22j0cjpy9j17y63zgd9m8j4qf7ldsg0jqm1vrym76w";
      })
      (fetchpatchTelethon {
        rev = "8224e5aabf18bb31c6af8c460c38ced11756f080";
        sha256 = "0x3xfkld4d2kc0a1a8ldxy85pi57zaipq3b401b16r6rzbi4sh1j";
      })
      (fetchpatchTelethon {
        rev = "aefa429236d28ae68bec4e4ef9f12d13f647dfe6";
        sha256 = "043hks8hg5sli1amfv5453h831nwy4dgyw8xr4xxfaxh74754icx";
      })
    ];
    generator-use-pathlib-open-to-1_5_3 = fetchpatchTelethon {
      rev = "b57e3e3e0a752903fe7d539fb87787ec6712a3d9";
      sha256 = "1rl3lkwfi3h62ppzglrmz13zfai8i8cchzqgbjccr4l7nzh1n6nq";
    };
    sort-generated-tlobjects-to-1_7_1 = fetchpatchTelethon {
      rev = "08f8aa3c526c043c107ec1b489b89c011555722f";
      sha256 = "1lkvvjzhm9jfrxpm4hbvvysz5f3qi0v4f7vqnfmrzawl73s8qk80";
    };
  };

  meta = let inherit (lib) licenses maintainers; in {
    description = "Full-featured Telegram client library for Python 3";
    fullDescription = ''
      Telegram is a popular messaging application. This library is meant to
      make it easy for you to write Python programs that can interact with
      Telegram. Think of it as a wrapper that has already done the heavy job
      for you, so you can focus on developing an application.
    '';
    homepage = https://github.com/LonamiWebs/Telethon;
    license = licenses.mit;
    maintainers = [ maintainers.bb010g maintainers.nyanloutre ];
  };
}
