{ pkgs ? import <nixpkgs> { }, enableEnvs ? true, useRelease ? true }:

# packages built against all Python versions (along with withPackages
# environments for testing)

# to use for testing, you'll probably want a variant of:
# ```sh
# nix-shell nix/extended.nix -A telethon-devel-python37 --run "python"
# ```

let
  inherit (pkgs.lib) attrNames attrValues concatMap head listToAttrs
    mapAttrsToList optional optionals tail;
  nurAttrs = import ../default.nix { inherit pkgs useRelease; };

  pyVersions = concatMap (n: optional (pkgs ? ${n}) n) [
    "python3"
    "python35"
    "python36"
    "python37"
    # "pypy3"
    # "pypy35"
    # "pypy36"
    # "pypy37"
  ];

  pyPkgEnvs = [
    [ "telethon" "telethon" ]
    [ "telethon-devel" "telethon-devel" ]

    [ "telethon_1" "telethon_1" ]
    [ "telethon_1_10" "telethon_1_10" ]
    [ "telethon_1_10_1" "telethon_1_10_1" ]
    [ "telethon_1_10_0" "telethon_1_10_0" ]
    [ "telethon_1_9" "telethon_1_9" ]
    [ "telethon_1_9_0" "telethon_1_9_0" ]
    [ "telethon_1_8" "telethon_1_8" ]
    [ "telethon_1_8_0" "telethon_1_8_0" ]
    [ "telethon_1_7" "telethon_1_7" ]
    [ "telethon_1_7_7" "telethon_1_7_7" ]
    [ "telethon_1_7_6" "telethon_1_7_6" ]
    [ "telethon_1_7_5" "telethon_1_7_5" ]
    [ "telethon_1_7_4" "telethon_1_7_4" ]
    [ "telethon_1_7_3" "telethon_1_7_3" ]
    [ "telethon_1_7_2" "telethon_1_7_2" ]
    [ "telethon_1_7_1" "telethon_1_7_1" ]
    [ "telethon_1_7_0" "telethon_1_7_0" ]
    [ "telethon_1_6" "telethon_1_6" ]
    [ "telethon_1_6_2" "telethon_1_6_2" ]
    [ "telethon_1_6_1" "telethon_1_6_1" ]
    [ "telethon_1_6_0" "telethon_1_6_0" ]
    [ "telethon_1_5" "telethon_1_5" ]
    [ "telethon_1_5_5" "telethon_1_5_5" ]
    [ "telethon_1_5_4" "telethon_1_5_4" ]
    [ "telethon_1_5_3" "telethon_1_5_3" ]
    [ "telethon_1_5_2" "telethon_1_5_2" ]
    [ "telethon_1_5_1" "telethon_1_5_1" ]
    [ "telethon_1_5_0" "telethon_1_5_0" ]
    [ "telethon_1_4" "telethon_1_4" ]
    [ "telethon_1_4_3" "telethon_1_4_3" ]
    # [ "telethon_1_4_2" "telethon_1_4_2" ]
    # [ "telethon_1_4_1" "telethon_1_4_1" ]
    # [ "telethon_1_4_0" "telethon_1_4_0" ]
  ];

  getPkgPair = pkgs: n: let p = pkgs.${n}; in { name = n; value = p; };
  getPkgPairs = pkgs: map (getPkgPair pkgs);
  pyPkgPairs = py:
    concatMap (d: map (getPkgPair py.pkgs) (tail d)) pyPkgEnvs;
  pyPkgEnvPair = pyNm: py: envNm: env: {
    name = "${envNm}-env-${pyNm}";
    value = (py.withPackages (ps: map (pn: ps.${pn}) env)).overrideAttrs (o: {
      name = "${envNm}-${py.name}-env";
      preferLocalBuild = true;
    });
  };
  pyNurPairs = pyNm: py:
    map ({ name, value }: { name = "${name}-${pyNm}"; inherit value; })
      (pyPkgPairs py) ++
    optionals enableEnvs
      (map (d: pyPkgEnvPair pyNm py (head d) (tail d)) pyPkgEnvs);
in nurAttrs // (listToAttrs (concatMap (py: let
  python = pkgs.${py}.override {
    packageOverrides = nurAttrs.pythonPackageOverrides;
  }; in
  pyNurPairs py python) pyVersions))
