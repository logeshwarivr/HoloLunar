using UnityEngine;
using UnityEngine.Rendering;

public class TerrainGenerator : MonoBehaviour
{
    [Header("Assign these in the Inspector")]
    [Tooltip("Fallback heightmap, used only if Height Data is empty.")]
    public Texture2D heightmapTexture;
    public Texture2D confidenceTexture;

    [Header("Real data (Chandrayaan-2 CPR + LOLA DEM)")]
    [Tooltip("web_valid_mask.png: white = valid CPR, black = no data (gaps between SAR strips).")]
    public Texture2D validMaskTexture;
    [Tooltip("faustini_height_2049.bytes: raw 16-bit little-endian heights, normalized 0..1.")]
    public TextAsset heightData;
    [Tooltip("Width and height of the raw height file in samples.")]
    public int heightDataSize = 2049;
    [Tooltip("Color drawn where the SAR mosaic has no data.")]
    public Color noDataColor = new Color(0.22f, 0.22f, 0.22f, 1f);

    [Header("Size")]
    public float terrainWidth = 300f;
    public float terrainLength = 300f;
    public float terrainHeight = 53.5f;

    [Header("Output type")]
    [Tooltip("OFF = Unity Terrain (desktop preview). ON = normal mesh. Turn ON for AR: Terrain ignores rotation/scale, a mesh does not.")]
    public bool buildAsMesh = false;

    [Tooltip("Terrain mode only. Must be 2^n + 1 (129, 257, 513, 1025).")]
    public int terrainResolution = 513;

    [Tooltip("Mesh mode only. Grid size (200 = 40,000 vertices, fine for phones).")]
    [Range(32, 400)]
    public int meshResolution = 200;

    [Tooltip("Mesh mode only. A URP/Lit material (Surface Type: Opaque). Assigning it here keeps the shader in Android builds.")]
    public Material meshMaterial;

    [Header("Clarity")]
    [Range(0, 8)]
    public int smoothPasses = 1;

    [Header("Overlay Settings")]
    [Range(0f, 1f)]
    [Tooltip("0 = plain gray terrain, 1 = full heatmap colors")]
    public float overlayOpacity = 0.85f;

    public bool alreadyPlaced = false;

    // Called externally by DemoSpawner / ARPlacement / TerrainOnTarget
    public GameObject GenerateTerrain()
    {
        int res = buildAsMesh ? meshResolution : terrainResolution;
        float[,] heights = BuildHeights(res);
        Texture2D heatmap = BuildHeatmapTexture();

        return buildAsMesh ? BuildMeshObject(heights, heatmap)
                           : BuildTerrainObject(heights, heatmap);
    }

    // ---------- Heights ----------
    float[,] BuildHeights(int res)
    {
        float[,] heights = new float[res, res];

        // Real heights from the raw 16-bit file (if assigned)
        float[,] raw = null;
        int n = heightDataSize;
        if (heightData != null)
        {
            byte[] b = heightData.bytes;
            if (b.Length < n * n * 2)
            {
                Debug.LogError("TerrainGenerator: height data is smaller than " + n + "x" + n +
                               " 16-bit samples. Re-run export_heightmap_raw.py. Falling back to heightmapTexture.");
            }
            else
            {
                raw = new float[n, n];
                for (int y = 0; y < n; y++)
                {
                    for (int x = 0; x < n; x++)
                    {
                        int i = (y * n + x) * 2;
                        raw[y, x] = (b[i] | (b[i + 1] << 8)) / 65535f;
                    }
                }
            }
        }

        if (raw == null && heightmapTexture == null)
        {
            Debug.LogError("TerrainGenerator: assign Height Data or Heightmap Texture.");
            return heights;
        }

        for (int y = 0; y < res; y++)
        {
            for (int x = 0; x < res; x++)
            {
                float u = x / (float)(res - 1);
                float v = y / (float)(res - 1);

                if (raw != null)
                {
                    // File row 0 is the top of the image; Unity v = 1 is the top, so flip.
                    float fx = u * (n - 1);
                    float fy = (1f - v) * (n - 1);
                    int x0 = Mathf.Min((int)fx, n - 2);
                    int y0 = Mathf.Min((int)fy, n - 2);
                    float tx = fx - x0;
                    float ty = fy - y0;
                    float h0 = Mathf.Lerp(raw[y0, x0], raw[y0, x0 + 1], tx);
                    float h1 = Mathf.Lerp(raw[y0 + 1, x0], raw[y0 + 1, x0 + 1], tx);
                    heights[y, x] = Mathf.Lerp(h0, h1, ty);
                }
                else
                {
                    heights[y, x] = heightmapTexture.GetPixelBilinear(u, v).grayscale;
                }
            }
        }

        for (int p = 0; p < smoothPasses; p++)
            heights = SmoothHeights(heights, res);
        return heights;
    }

    // ---------- Option 1: Unity Terrain (desktop preview) ----------
    GameObject BuildTerrainObject(float[,] heights, Texture2D heatmap)
    {
        int res = heights.GetLength(0);

        TerrainData terrainData = new TerrainData();
        terrainData.heightmapResolution = res;
        terrainData.size = new Vector3(terrainWidth, terrainHeight, terrainLength);
        terrainData.SetHeights(0, 0, heights);

        TerrainLayer layer = new TerrainLayer();
        layer.diffuseTexture = heatmap;
        layer.tileSize = new Vector2(terrainWidth, terrainLength);
        layer.tileOffset = Vector2.zero;
        layer.metallic = 0f;
        layer.smoothness = 0f;
        terrainData.terrainLayers = new TerrainLayer[] { layer };

        int a = terrainData.alphamapResolution;
        float[,,] alpha = new float[a, a, 1];
        for (int y = 0; y < a; y++)
            for (int x = 0; x < a; x++)
                alpha[y, x, 0] = 1f;
        terrainData.SetAlphamaps(0, 0, alpha);

        GameObject terrainObj = Terrain.CreateTerrainGameObject(terrainData);
        terrainObj.name = "FaustiniTerrain";
        terrainObj.transform.position = new Vector3(-terrainWidth / 2f, 0, -terrainLength / 2f);
        return terrainObj;
    }

    // ---------- Option 2: Mesh (use this for AR) ----------
    // Centered on its own origin, so parenting it under the Image Target
    // puts the middle of the terrain on the middle of the printed target.
    GameObject BuildMeshObject(float[,] heights, Texture2D heatmap)
    {
        int n = heights.GetLength(0);
        Vector3[] verts = new Vector3[n * n];
        Vector2[] uvs = new Vector2[n * n];
        int[] tris = new int[(n - 1) * (n - 1) * 6];

        for (int z = 0; z < n; z++)
        {
            for (int x = 0; x < n; x++)
            {
                float u = x / (float)(n - 1);
                float v = z / (float)(n - 1);
                int i = z * n + x;
                verts[i] = new Vector3((u - 0.5f) * terrainWidth,
                                       heights[z, x] * terrainHeight,
                                       (v - 0.5f) * terrainLength);
                uvs[i] = new Vector2(u, v);
            }
        }

        int t = 0;
        for (int z = 0; z < n - 1; z++)
        {
            for (int x = 0; x < n - 1; x++)
            {
                int i = z * n + x;
                tris[t++] = i;     tris[t++] = i + n;     tris[t++] = i + 1;
                tris[t++] = i + 1; tris[t++] = i + n;     tris[t++] = i + n + 1;
            }
        }

        Mesh mesh = new Mesh();
        mesh.name = "FaustiniMesh";
        mesh.indexFormat = (n * n > 65000) ? IndexFormat.UInt32 : IndexFormat.UInt16;
        mesh.vertices = verts;
        mesh.uv = uvs;
        mesh.triangles = tris;
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();

        Material mat;
        if (meshMaterial != null)
        {
            mat = new Material(meshMaterial);
        }
        else
        {
            Shader s = Shader.Find("Universal Render Pipeline/Lit");
            if (s == null) s = Shader.Find("Universal Render Pipeline/Unlit");
            if (s == null)
            {
                Debug.LogError("TerrainGenerator: assign a URP material to 'Mesh Material'.");
                s = Shader.Find("Sprites/Default");
            }
            mat = new Material(s);
        }
        mat.SetTexture("_BaseMap", heatmap);
        mat.SetColor("_BaseColor", Color.white);
        if (mat.HasProperty("_Smoothness")) mat.SetFloat("_Smoothness", 0f);

        GameObject obj = new GameObject("FaustiniTerrain");
        obj.AddComponent<MeshFilter>().sharedMesh = mesh;
        obj.AddComponent<MeshRenderer>().sharedMaterial = mat;
        return obj;
    }

    // ---------- Helpers ----------
    float[,] SmoothHeights(float[,] src, int res)
    {
        float[,] dst = new float[res, res];
        for (int y = 0; y < res; y++)
        {
            for (int x = 0; x < res; x++)
            {
                float sum = 0f;
                int count = 0;
                for (int dy = -1; dy <= 1; dy++)
                {
                    for (int dx = -1; dx <= 1; dx++)
                    {
                        int ny = y + dy, nx = x + dx;
                        if (ny < 0 || ny >= res || nx < 0 || nx >= res) continue;
                        sum += src[ny, nx];
                        count++;
                    }
                }
                dst[y, x] = sum / count;
            }
        }
        return dst;
    }

    Texture2D BuildHeatmapTexture()
    {
        int w = confidenceTexture.width;
        int h = confidenceTexture.height;

        Color[] src = confidenceTexture.GetPixels();
        Color[] dst = new Color[src.Length];
        Color neutral = new Color(0.55f, 0.55f, 0.55f, 1f);

        // Optional no-data mask (white = valid, black = no data)
        Color[] mask = null;
        int mw = 0, mh = 0;
        if (validMaskTexture != null)
        {
            mask = validMaskTexture.GetPixels();
            mw = validMaskTexture.width;
            mh = validMaskTexture.height;
        }

        for (int i = 0; i < src.Length; i++)
        {
            if (mask != null)
            {
                int x = i % w;
                int y = i / w;
                int mx = Mathf.Clamp(Mathf.RoundToInt(x / (float)(w - 1) * (mw - 1)), 0, mw - 1);
                int my = Mathf.Clamp(Mathf.RoundToInt(y / (float)(h - 1) * (mh - 1)), 0, mh - 1);
                if (mask[my * mw + mx].grayscale < 0.5f)
                {
                    dst[i] = noDataColor;
                    continue;
                }
            }

            Color heat = GetHeatmapColor(src[i].grayscale);
            Color c = Color.Lerp(neutral, heat, overlayOpacity);
            c.a = 1f;
            dst[i] = c;
        }

        Texture2D tex = new Texture2D(w, h, TextureFormat.RGBA32, true);
        tex.wrapMode = TextureWrapMode.Clamp;
        tex.filterMode = FilterMode.Bilinear;
        tex.anisoLevel = 8;
        tex.SetPixels(dst);
        tex.Apply();
        return tex;
    }

    // low value = blue ... high value = red
    Color GetHeatmapColor(float v)
    {
        if (v < 0.33f)
        {
            float t = v / 0.33f;
            return new Color(0, t, 1, 1);
        }
        else if (v < 0.66f)
        {
            float t = (v - 0.33f) / 0.33f;
            return new Color(t, 1, 1 - t, 1);
        }
        else
        {
            float t = (v - 0.66f) / 0.34f;
            return new Color(1, 1 - t, 0, 1);
        }
    }
}