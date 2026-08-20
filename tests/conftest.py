from __future__ import annotations

from pathlib import Path

import pytest

POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <artifactId>pedidos-api</artifactId>
  <dependencies>
    <dependency>
      <groupId>com.exemplo</groupId>
      <artifactId>pedidos-raml</artifactId>
      <version>1.1.54</version>
      <classifier>raml</classifier>
      <type>zip</type>
    </dependency>
  </dependencies>
</project>
"""


def make_api(root: Path, name: str = "pedidos-api") -> Path:
    api = root / name
    (api / "src" / "main" / "mule").mkdir(parents=True)
    (api / "pom.xml").write_text(POM, encoding="utf-8")
    (api / "src" / "main" / "mule" / "application.xml").write_text("<mule/>", encoding="utf-8")
    (api / "target").mkdir()
    (api / "target" / "junk.jar").write_text("x", encoding="utf-8")
    return api


def make_raml(root: Path, name: str = "pedidos-raml") -> Path:
    raml = root / name
    raml.mkdir(parents=True)
    (raml / "api.raml").write_text("#%RAML 1.0\ntitle: pedidos\n", encoding="utf-8")
    return raml


@pytest.fixture
def workspace(tmp_path: Path) -> dict[str, Path]:
    """Um repositório de trabalho e um workspace do Studio, ambos já populados."""
    work, studio = tmp_path / "work", tmp_path / "studio"
    work.mkdir()
    studio.mkdir()
    make_api(work)
    make_raml(work)
    make_api(studio, "studio-pedidos")
    make_raml(studio, "studio-pedidos-raml")
    return {"work": work, "studio": studio}
