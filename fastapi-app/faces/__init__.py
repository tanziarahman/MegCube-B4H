"""Telling people apart by face, for "different people" in people counting.

  embedder   a face picture -> a 128-number fingerprint (OpenCV YuNet + SFace)
  worker     fingerprints new walk-pasts after each poll (sightings.face_embedding)
  grouping   counts different people among the fingerprints of a period, as a range
  download   fetches the two model files (uv run python -m faces.download)
"""
