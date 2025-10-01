{
  description = "Python venv development template";

  inputs = {
    utils.url = "github:numtide/flake-utils";
    nur = {
      url = "github:nix-community/NUR";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      utils,
      nur,
      ...
    }:
    utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;

          overlays = [ nur.overlays.default ];
        };
      in
      {
        packages.default =
          with pkgs.python3Packages;
          buildPythonPackage rec {
            pname = "linhai";
            # it takes minutes
            doCheck = false;
            pyproject = true;

            nativeBuildInputs = [ pkgs.installShellFiles ];

            build-system = [
              setuptools
              setuptools-scm
            ];

            dependencies = [
              pkgs.nur.repos.marven11.fenjing
              openai
              httpx
              beautifulsoup4
              mistune
              requests
              textual
              selenium
            ];

            src = ./.;
            version = "0.0.1";
          };
      }
    );
}
