{ lib, buildPythonPackage, nix-gitignore, pythonOlder
, async_generator, pyaes, rsa
}:

let
  common = import ./common.nix { inherit lib; };
in buildPythonPackage rec {
  pname = "telethon";
  # If pinning to a specific commit, use the following output instead:
  # ```sh
  # TZ=UTC git show -s --format=format:%cd --date=short-local
  # ```
  version = "HEAD";

  src = nix-gitignore.gitignoreSource ''
    /.git
    /default.nix
    /nix
  '' ../..;

  propagatedBuildInputs = [ async_generator rsa pyaes ];

  doCheck = false; # No tests available

  disabled = pythonOlder "3.5";
  meta = common.meta;
}
