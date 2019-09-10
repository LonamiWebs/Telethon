# A NUR-compatible package specification.
{ pkgs ? import <nixpkgs> {}, useRelease ? true }:

rec {
  # The `lib`, `modules`, and `overlay` names are special
  lib = ({ pkgs }: { }) { inherit pkgs; }; # functions
  modules = { }; # NixOS modules
  overlays = { }; # nixpkgs overlays

  # # development

  # ## development.python-modules

  # use in a shell like
  # ```nix
  # ((pkgs.python3.override {
  #   packageOverrides = pythonPackageOverrides;
  # }).withPackages (ps: [ ps.telethon ])).env
  # ```
  pythonPackageOverrides = self: super: let
    defaultTelethonArgs = { inherit useRelease; };
    telethonPkg = v: args: self.callPackage (./nix/telethon + "/${v}.nix")
      (defaultTelethonArgs // args);
  in rec {
    telethon = telethon_1;
    telethon-devel = self.callPackage ./nix/telethon/devel.nix { };

    telethon_1 = telethon_1_10;
    telethon_1_10 = telethon_1_10_1;
    telethon_1_10_1 = telethonPkg "1.10" { version = "1.10.1"; };
    telethon_1_10_0 = telethonPkg "1.10" { version = "1.10.0"; };
    telethon_1_9 = telethon_1_9_0;
    telethon_1_9_0 = telethonPkg "1.9" { version = "1.9.0"; };
    telethon_1_8 = telethon_1_8_0;
    telethon_1_8_0 = telethonPkg "1.8" { version = "1.8.0"; };
    telethon_1_7 = telethon_1_7_7;
    telethon_1_7_7 = telethonPkg "1.7" { version = "1.7.7"; };
    telethon_1_7_6 = telethonPkg "1.7" { version = "1.7.6"; };
    telethon_1_7_5 = telethonPkg "1.7" { version = "1.7.5"; };
    telethon_1_7_4 = telethonPkg "1.7" { version = "1.7.4"; };
    telethon_1_7_3 = telethonPkg "1.7" { version = "1.7.3"; };
    telethon_1_7_2 = telethonPkg "1.7" { version = "1.7.2"; };
    telethon_1_7_1 = telethonPkg "1.7" { version = "1.7.1"; };
    telethon_1_7_0 = telethonPkg "1.7" { version = "1.7.0"; };
    telethon_1_6 = telethon_1_6_2;
    telethon_1_6_2 = telethonPkg "1.6" { version = "1.6.2"; };
    # 1.6.1.post1: hotpatch that fixed Telethon.egg-info dir perms
    telethon_1_6_1 = telethonPkg "1.6" { version = "1.6.1"; };
    telethon_1_6_0 = telethonPkg "1.6" { version = "1.6.0"; };
    telethon_1_5 = telethon_1_5_5;
    telethon_1_5_5 = telethonPkg "1.5" { version = "1.5.5"; };
    telethon_1_5_4 = telethonPkg "1.5" { version = "1.5.4"; };
    telethon_1_5_3 = telethonPkg "1.5" { version = "1.5.3"; };
    telethon_1_5_2 = telethonPkg "1.5" { version = "1.5.2"; };
    telethon_1_5_1 = telethonPkg "1.5" { version = "1.5.1"; };
    telethon_1_5_0 = telethonPkg "1.5" { version = "1.5.0"; };
    telethon_1_4 = telethon_1_4_3;
    telethon_1_4_3 = telethonPkg "1.4" { version = "1.4.3"; };
    telethon_1_4_2 = telethonPkg "1.4" { version = "1.4.2"; };
    telethon_1_4_1 = telethonPkg "1.4" { version = "1.4.1"; };
    telethon_1_4_0 = telethonPkg "1.4" { version = "1.4.0"; };
    #telethon_1_3_0
    #telethon_1_2_0
    #telethon_1_1_1
    #telethon_1_1_0
    #telethon_1_0_4
    #telethon_1_0_3
    #telethon_1_0_2
    #telethon_1_0_1
    #telethon_1_0_0-rc1
    #telethon_1_0_0
    #telethon_0_19_1
    #telethon_0_19_0
    #telethon_0_18_3
    #telethon_0_18_2
    #telethon_0_18_1
    #telethon_0_18_0
    #telethon_0_17_4
    #telethon_0_17_3
    #telethon_0_17_2
    #telethon_0_17_1
    #telethon_0_17_0
    #telethon_0_16_2
    #telethon_0_16_1
    #telethon_0_16_0
    #telethon_0_15_5
    #telethon_0_15_4
    #telethon_0_15_3
    #telethon_0_15_2
    #telethon_0_15_1
    #telethon_0_15_0
    #telethon_0_14_2
    #telethon_0_14_1
    #telethon_0_14_0
    #telethon_0_13_6
    #telethon_0_13_5
    #telethon_0_13_4
    #telethon_0_13_3
    #telethon_0_13_2
    #telethon_0_13_1
    #telethon_0_13_0
    #telethon_0_12_2
    #telethon_0_12_1
    #telethon_0_12_0
    #telethon_0_11_5
    #telethon_0_11_4
    #telethon_0_11_3
    #telethon_0_11_2
    #telethon_0_11_1
    #telethon_0_11_0
    #telethon_0_10_1
    #telethon_0_10_0
    #telethon_0_9_1
    #telethon_0_9_0
    #telethon_0_8_0
    #telethon_0_7_1
    #telethon_0_7_0
    #telethon_0_6_0
    #telethon_0_5_0
    #telethon_0_4_0
    #telethon_0_3_0
    #telethon_0_2_0
    #telethon_0_1_0
  };
}

