using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.Rendering;
using Vuforia;

// Whole-Moon globe with a Faustini marker.
//  - Drag to rotate, pinch / mouse wheel to zoom.
//  - Zoom in far enough (or tap the marker) and the globe is replaced by the detailed
//    Faustini terrain (real Chandrayaan-2 CPR on LOLA relief) built by TerrainGenerator.
//  - Zoom the detailed terrain out (PinchZoom) and you return to the globe.
//
// DESKTOP SCENE: put on an empty GameObject, "Use Image Target" OFF, disable DemoSpawner.
// AR SCENE:      put on the Vuforia Image Target, "Use Image Target" ON,
//                disable TerrainOnTarget and ARPlacement (this script replaces them).
public class MoonGlobe : MonoBehaviour
{
    enum Mode { Globe, Detail }

    [Header("Globe")]
    [Tooltip("Equirectangular Moon color map, centered on 0 deg longitude (NASA SVS CGI Moon Kit).")]
    public Texture2D moonColorMap;
    [Tooltip("URP/Lit material. It is copied and the texture is set on the copy. Assign it so the shader is kept in Android builds.")]
    public Material globeMaterial;
    [Tooltip("Desktop only. In AR the radius is taken from the Image Target size.")]
    public float globeRadius = 100f;
    [Range(32, 256)] public int longitudeSegments = 128;
    [Range(16, 128)] public int latitudeSegments = 64;

    [Header("Faustini marker")]
    public float faustiniLatitude = -87.3f;
    public float faustiniLongitude = 77.0f;
    [Tooltip("Marker size as a fraction of the globe radius.")]
    public float markerSizeFraction = 0.03f;
    public Color markerColor = new Color(1f, 0.2f, 0.1f, 1f);
    [Tooltip("How close (pixels) a tap must be to the marker to open the detail view.")]
    public float tapRadiusPixels = 90f;

    [Header("Detail terrain")]
    [Tooltip("The TerrainGenerator that holds the real heights and CPR textures.")]
    public TerrainGenerator generator;
    [Tooltip("Width of the detail terrain in scene units. Desktop only; in AR it is the Image Target width.")]
    public float detailWorldSize = 160f;
    [Tooltip("Zooming the detail terrain below this scale returns to the globe (PinchZoom min is 0.2).")]
    public float backToGlobeScale = 0.3f;

    [Header("Controls")]
    public float rotateSpeed = 0.25f;
    public float minGlobeScale = 0.6f;
    public float maxGlobeScale = 3f;
    [Tooltip("Globe zoom at which the detail view opens (if Faustini faces the camera).")]
    public float detailThreshold = 2.6f;
    [Tooltip("Max angle (deg) between Faustini and the camera direction to open the detail view.")]
    public float focusAngle = 25f;
    public float focusSpeed = 4f;
    public float mouseWheelSpeed = 0.1f;
    public bool startFacingFaustini = true;

    [Header("Desktop preview")]
    [Tooltip("Moves Camera.main to frame the globe / terrain. Forced OFF in AR.")]
    public bool frameCamera = true;

    [Header("AR (Vuforia)")]
    [Tooltip("ON when this script is on the Image Target in the AR scene.")]
    public bool useImageTarget = false;
    [Tooltip("Globe radius as a fraction of the Image Target width.")]
    public float globeRadiusFraction = 0.4f;
    [Tooltip("Used only if the Image Target size can not be read.")]
    public float fallbackTargetWidth = 0.15f;

    Mode mode = Mode.Globe;
    Transform pivot;          // rotates and scales (the globe)
    Transform marker;
    float markerWorldSize;
    GameObject detailRoot;
    GameObject detailTerrain;

    bool dragging, moved, focusing;
    Vector2 downPos, lastMouse;
    float lastPinch;
    Quaternion focusTarget;

    // ---------- Setup ----------
    void Start()
    {
        if (useImageTarget)
        {
            frameCamera = false;
            float width = 0f;
            ImageTargetBehaviour target = GetComponent<ImageTargetBehaviour>();
            if (target == null) target = GetComponentInParent<ImageTargetBehaviour>();
            if (target != null) width = target.GetSize().x;
            if (width <= 0f)
            {
                width = fallbackTargetWidth;
                Debug.LogWarning("MoonGlobe: could not read Image Target size, using " + width);
            }
            globeRadius = width * globeRadiusFraction;
            detailWorldSize = width;
        }

        BuildGlobe();

        if (useImageTarget)
        {
            // Faustini (south pole region) faces up from the printed target
            pivot.localRotation = Quaternion.FromToRotation(marker.localPosition.normalized, Vector3.up);
            // Hidden until Vuforia finds the target (its Default Observer Event Handler re-enables renderers)
            foreach (Renderer r in pivot.GetComponentsInChildren<Renderer>()) r.enabled = false;
        }
        else
        {
            FrameCamera(false);
            if (startFacingFaustini) FocusFaustini(true);
        }
    }

    void BuildGlobe()
    {
        GameObject p = new GameObject("MoonPivot");
        p.transform.SetParent(transform, false);
        pivot = p.transform;

        GameObject sphere = new GameObject("MoonSphere");
        sphere.transform.SetParent(pivot, false);
        sphere.AddComponent<MeshFilter>().sharedMesh = BuildSphereMesh();

        Material mat;
        if (globeMaterial != null) mat = new Material(globeMaterial);
        else mat = new Material(FindShader());
        if (moonColorMap != null)
        {
            if (mat.HasProperty("_BaseMap")) mat.SetTexture("_BaseMap", moonColorMap);
            else mat.mainTexture = moonColorMap;
        }
        else Debug.LogWarning("MoonGlobe: assign 'Moon Color Map' (NASA CGI Moon Kit color map).");
        if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", Color.white);
        if (mat.HasProperty("_Smoothness")) mat.SetFloat("_Smoothness", 0f);
        sphere.AddComponent<MeshRenderer>().sharedMaterial = mat;

        // Faustini marker
        markerWorldSize = globeRadius * markerSizeFraction;
        GameObject m = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        m.name = "FaustiniMarker";
        Destroy(m.GetComponent<Collider>());   // taps are detected in screen space
        m.transform.SetParent(pivot, false);
        m.transform.localPosition = LatLonToLocal(faustiniLatitude, faustiniLongitude, globeRadius * 1.005f);
        m.transform.localScale = Vector3.one * markerWorldSize;
        Material mm = globeMaterial != null ? new Material(globeMaterial) : new Material(FindShader());
        mm.mainTexture = null;
        if (mm.HasProperty("_BaseMap")) mm.SetTexture("_BaseMap", null);
        if (mm.HasProperty("_BaseColor")) mm.SetColor("_BaseColor", markerColor);
        mm.color = markerColor;
        m.GetComponent<MeshRenderer>().sharedMaterial = mm;
        marker = m.transform;
    }

    static Shader FindShader()
    {
        Shader s = Shader.Find("Universal Render Pipeline/Lit");
        if (s == null) s = Shader.Find("Universal Render Pipeline/Unlit");
        if (s == null) s = Shader.Find("Sprites/Default");
        return s;
    }

    // lon 0 faces +Z, east is to the viewer's right when looking at the globe from outside.
    static Vector3 LatLonToLocal(float latDeg, float lonDeg, float r)
    {
        float la = latDeg * Mathf.Deg2Rad;
        float lo = lonDeg * Mathf.Deg2Rad;
        return new Vector3(-Mathf.Cos(la) * Mathf.Sin(lo), Mathf.Sin(la), Mathf.Cos(la) * Mathf.Cos(lo)) * r;
    }

    Mesh BuildSphereMesh()
    {
        int cols = longitudeSegments + 1;
        int rows = latitudeSegments + 1;
        Vector3[] verts = new Vector3[cols * rows];
        Vector3[] normals = new Vector3[cols * rows];
        Vector2[] uvs = new Vector2[cols * rows];

        for (int i = 0; i < rows; i++)
        {
            float v = i / (float)latitudeSegments;
            float lat = Mathf.Lerp(-90f, 90f, v);
            for (int j = 0; j < cols; j++)
            {
                float u = j / (float)longitudeSegments;
                float lon = Mathf.Lerp(-180f, 180f, u);
                int idx = i * cols + j;
                verts[idx] = LatLonToLocal(lat, lon, globeRadius);
                normals[idx] = verts[idx].normalized;
                uvs[idx] = new Vector2(u, v);
            }
        }

        int[] tris = new int[(rows - 1) * (cols - 1) * 6];
        int t = 0;
        for (int i = 0; i < rows - 1; i++)
        {
            for (int j = 0; j < cols - 1; j++)
            {
                int a = i * cols + j;
                int b = a + cols;
                int c = a + 1;
                int d = b + 1;
                tris[t++] = a; tris[t++] = b; tris[t++] = c;
                tris[t++] = b; tris[t++] = d; tris[t++] = c;
            }
        }

        Mesh mesh = new Mesh();
        mesh.name = "MoonSphere";
        mesh.indexFormat = IndexFormat.UInt32;
        mesh.vertices = verts;
        mesh.normals = normals;
        mesh.uv = uvs;
        mesh.triangles = tris;
        mesh.RecalculateBounds();
        return mesh;
    }

    // ---------- Update ----------
    void Update()
    {
        if (pivot == null) return;

        if (mode == Mode.Globe) UpdateGlobe();
        else UpdateDetail();

        if (mode == Mode.Globe && marker != null)
        {
            float pulse = 1f + 0.25f * Mathf.Sin(Time.time * 3f);
            marker.localScale = Vector3.one * markerWorldSize * pulse;
        }
    }

    void UpdateGlobe()
    {
        HandleFocus();

        if (Input.touchCount >= 2)
        {
            Touch a = Input.GetTouch(0);
            Touch b = Input.GetTouch(1);
            float d = Vector2.Distance(a.position, b.position);
            if (a.phase == TouchPhase.Began || b.phase == TouchPhase.Began) lastPinch = d;
            else if (lastPinch > 1f) ZoomGlobe(d / lastPinch);
            lastPinch = d;
            dragging = false;
        }
        else
        {
            lastPinch = 0f;

            if (Input.touchCount == 1)
            {
                Touch t = Input.GetTouch(0);
                if (t.phase == TouchPhase.Began)
                {
                    dragging = !OverUI(t.fingerId);
                    moved = false;
                    downPos = t.position;
                }
                else if (dragging && t.phase == TouchPhase.Moved)
                {
                    RotateGlobe(t.deltaPosition);
                    if ((t.position - downPos).magnitude > 12f) moved = true;
                }
                else if (dragging && t.phase == TouchPhase.Ended)
                {
                    if (!moved) TryTap(t.position);
                    dragging = false;
                }
            }
            else
            {
                Vector2 m = Input.mousePosition;
                if (Input.GetMouseButtonDown(0))
                {
                    dragging = !OverUI(-1);
                    moved = false;
                    downPos = m;
                    lastMouse = m;
                }
                else if (dragging && Input.GetMouseButton(0))
                {
                    Vector2 delta = m - lastMouse;
                    lastMouse = m;
                    if (delta.sqrMagnitude > 0f) RotateGlobe(delta);
                    if ((m - downPos).magnitude > 12f) moved = true;
                }
                else if (dragging && Input.GetMouseButtonUp(0))
                {
                    if (!moved) TryTap(m);
                    dragging = false;
                }

                float wheel = Input.mouseScrollDelta.y;
                if (Mathf.Abs(wheel) > 0.001f) ZoomGlobe(1f + wheel * mouseWheelSpeed);
            }
        }

        if (mode == Mode.Globe && pivot.localScale.x >= detailThreshold)
        {
            if (AngleToCamera() <= focusAngle) ShowDetail();
            else FocusFaustini(false);
        }
    }

    void UpdateDetail()
    {
        if (detailTerrain == null) { ShowGlobe(); return; }
        if (detailTerrain.transform.localScale.x <= backToGlobeScale) ShowGlobe();
    }

    // ---------- Globe interaction ----------
    void RotateGlobe(Vector2 delta)
    {
        focusing = false;
        pivot.Rotate(Vector3.up, -delta.x * rotateSpeed, Space.World);
        pivot.Rotate(Vector3.right, delta.y * rotateSpeed, Space.World);
    }

    void ZoomGlobe(float factor)
    {
        float s = Mathf.Clamp(pivot.localScale.x * factor, minGlobeScale, maxGlobeScale);
        pivot.localScale = Vector3.one * s;
    }

    // Hook these to UI Buttons (OnClick)
    public void ZoomIn()  { if (mode == Mode.Globe) ZoomGlobe(1.25f); }
    public void ZoomOut() { if (mode == Mode.Globe) ZoomGlobe(0.8f); }
    public void FocusFaustiniButton() { if (mode == Mode.Globe) FocusFaustini(false); }

    void TryTap(Vector2 screenPos)
    {
        Camera cam = Camera.main;
        if (cam == null || marker == null) return;
        Vector3 sp = cam.WorldToScreenPoint(marker.position);
        if (sp.z <= 0f) return;
        Vector3 normal = (marker.position - pivot.position).normalized;
        Vector3 toCam = (cam.transform.position - marker.position).normalized;
        if (Vector3.Dot(normal, toCam) < 0.05f) return;   // marker is on the far side
        if (Vector2.Distance(screenPos, new Vector2(sp.x, sp.y)) <= tapRadiusPixels) ShowDetail();
    }

    float AngleToCamera()
    {
        Camera cam = Camera.main;
        if (cam == null || marker == null) return 180f;
        Vector3 markerDir = (marker.position - pivot.position).normalized;
        Vector3 camDir = (cam.transform.position - pivot.position).normalized;
        return Vector3.Angle(markerDir, camDir);
    }

    // Rotates the globe so Faustini faces the camera.
    public void FocusFaustini(bool instant)
    {
        Camera cam = Camera.main;
        if (cam == null || marker == null) return;
        Vector3 markerDir = (marker.position - pivot.position).normalized;
        Vector3 camDir = (cam.transform.position - pivot.position).normalized;
        focusTarget = Quaternion.FromToRotation(markerDir, camDir) * pivot.rotation;
        focusing = true;
        if (instant) { pivot.rotation = focusTarget; focusing = false; }
    }

    void HandleFocus()
    {
        if (!focusing) return;
        pivot.rotation = Quaternion.Slerp(pivot.rotation, focusTarget, Time.deltaTime * focusSpeed);
        if (Quaternion.Angle(pivot.rotation, focusTarget) < 0.5f) focusing = false;
    }

    // ---------- Switching views ----------
    public void ShowDetail()
    {
        if (mode == Mode.Detail) return;
        if (generator == null)
        {
            Debug.LogError("MoonGlobe: assign the TerrainGenerator to 'Generator'.");
            return;
        }

        generator.buildAsMesh = true;                 // zoom and AR need a mesh, not a Unity Terrain
        GameObject terrain = generator.GenerateTerrain();

        detailRoot = new GameObject("FaustiniDetailRoot");
        detailRoot.transform.SetParent(transform, false);
        detailRoot.transform.localScale = Vector3.one * (detailWorldSize / generator.terrainWidth);

        terrain.transform.SetParent(detailRoot.transform, false);
        terrain.transform.localPosition = Vector3.zero;
        terrain.transform.localRotation = Quaternion.identity;
        terrain.transform.localScale = Vector3.one;   // PinchZoom scales this one
        detailTerrain = terrain;

        pivot.gameObject.SetActive(false);
        mode = Mode.Detail;
        dragging = false;
        FrameCamera(true);
    }

    public void ShowGlobe()
    {
        if (detailRoot != null) Destroy(detailRoot);
        detailRoot = null;
        detailTerrain = null;

        pivot.gameObject.SetActive(true);
        pivot.localScale = Vector3.one;
        mode = Mode.Globe;
        FrameCamera(false);
    }

    void FrameCamera(bool detail)
    {
        if (!frameCamera || useImageTarget) return;
        Camera cam = Camera.main;
        if (cam == null) return;
        Vector3 c = transform.position;
        float r = globeRadius;
        Vector3 offset = detail ? new Vector3(0f, r * 1.3f, -r * 1.9f) : new Vector3(0f, 0f, -r * 3.2f);
        cam.transform.position = c + offset;
        cam.transform.LookAt(c + (detail ? Vector3.up * r * 0.1f : Vector3.zero));
    }

    static bool OverUI(int fingerId)
    {
        if (EventSystem.current == null) return false;
        return fingerId >= 0 ? EventSystem.current.IsPointerOverGameObject(fingerId)
                             : EventSystem.current.IsPointerOverGameObject();
    }
}