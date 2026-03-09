{
  description = "Python venv development template";

  inputs = {
    utils.url = "github:numtide/flake-utils";
    nur = {
      url = "github:nix-community/NUR";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    etherGhost = {
      url = "github:Marven11/EtherGhost/dev";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      utils,
      nur,
      etherGhost,
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
              hatchling
            ];

            dependencies = [
              etherGhost.packages.${system}.default
              openai
              httpx
              beautifulsoup4
              mistune
              textual
              selenium
              mcp
              pyte
              pydantic
              chardet
              bashlex
              tiktoken
              pillow
              tomli-w
            ];

            src = ./.;
            version = "0.1.0";
          };
      }
    );
}
