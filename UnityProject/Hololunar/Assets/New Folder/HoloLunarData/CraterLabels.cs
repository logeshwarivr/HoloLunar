using System.Collections.Generic;
using UnityEngine;
using TMPro;

// Adds white markers + name labels for other validated craters (Haworth, Shoemaker)
// and a name label for the red Faustini marker. Does not change MoonGlobe.
// Attach to the SAME GameObject as MoonGlobe (the ImageTarget in the AR scene).
public class CraterLabels : MonoBehaviour
{
    [System.Serializable]
    public class Crater
    {
        public string craterName = "Crater";
        public float latitude;
        public float longitude;
        public Color color = Color.white;
        [Tooltip("Label direction around the marker in degrees (0 = right, 90 = up, 180 = left, 270 = down).")]
        public float labelAngle = 0f;
    }

    [Header("Other validated craters (white markers)")]
    public Crater[] craters = new Crater[]
    {
        new Crater { craterName = "Haworth",   latitude = -87.5f, longitude = -5f, color = Color.white, labelAngle = 180f },
        new Crater { craterName = "Shoemaker", latitude = -88.1f, longitude = 45f, color = Color.white, labelAngle = 0f }
    };

    [Header("Faustini label (the red marker already exists)")]
    public bool labelFaustini = true;
    public float faustiniLabelAngle = 90f;

    [Header("Look")]
    [Tooltip("Marker size as a fraction of the globe radius.")]
    public float markerSizeFraction = 0.02f;
    [Tooltip("Text height as a fraction of the globe radius.")]
    public float labelSizeFraction = 0.06f;
    [Tooltip("Distance of the label from its marker, as a fraction of the globe radius.")]
    public float labelDistanceFraction = 0.12f;
    [Tooltip("Labels appear only when the globe is zoomed to at least this scale. Use 0 to always show.")]
    public float labelMinGlobeScale = 1.2f;
    public Color labelColor = Color.white;
    [Tooltip("Moves labels toward the camera so the Moon surface does not cut them off.")]
    public float labelLiftFraction = 0.15f;
    [Tooltip("Thickness of the line from marker to label, as a fraction of the globe radius.")]
    public float lineWidthFraction = 0.004f;

    class Entry
    {
        public Transform root;
        public Transform label;
        public LineRenderer line;
        public float angle;
    }

    MoonGlobe globe;
    Transform pivot;
    MeshRenderer sphereRenderer;
    readonly List<Entry> entries = new List<Entry>();
    bool built;

    void Awake()
    {
        globe = GetComponent<MoonGlobe>();
        if (globe == null) Debug.LogError("CraterLabels: put this script on the same object as MoonGlobe.");
    }

    void Update()
    {
        if (globe == null) return;

        if (!built)
        {
            Transform p = transform.Find("MoonPivot");
            if (p == null) return;
            Transform s = p.Find("MoonSphere");
            if (s == null) return;
            pivot = p;
            sphereRenderer = s.GetComponent<MeshRenderer>();
            Build();
            built = true;
        }

        Camera cam = Camera.main;
        if (cam == null || pivot == null) return;

        bool tracked = sphereRenderer != null && sphereRenderer.enabled;
        float scale = pivot.lossyScale.x;
        bool zoomedEnough = pivot.localScale.x >= labelMinGlobeScale;

        foreach (Entry e in entries)
        {
            Vector3 center = e.root.position;
            Vector3 normal = (center - pivot.position).normalized;
            Vector3 toCam = (cam.transform.position - center).normalized;
            bool show = tracked && zoomedEnough && Vector3.Dot(normal, toCam) > 0.15f;

            e.label.gameObject.SetActive(show);
            e.line.enabled = show;
            if (!show) continue;

            float a = e.angle * Mathf.Deg2Rad;
            Vector3 dir = cam.transform.right * Mathf.Cos(a) + cam.transform.up * Mathf.Sin(a);
            float world = globe.globeRadius * scale;
            Vector3 offset = dir * (world * labelDistanceFraction) + toCam * (world * labelLiftFraction);

            e.label.position = center + offset;
            e.label.rotation = Quaternion.LookRotation(e.label.position - cam.transform.position, cam.transform.up);

            float w = world * lineWidthFraction;
            e.line.startWidth = w;
            e.line.endWidth = w;
            e.line.SetPosition(0, center + toCam * (world * 0.003f));
            e.line.SetPosition(1, center + offset * 0.7f);
        }
    }

    void Build()
    {
        if (labelFaustini)
            AddEntry("Faustini", globe.faustiniLatitude, globe.faustiniLongitude, globe.markerColor, faustiniLabelAngle, false);

        foreach (Crater c in craters)
            AddEntry(c.craterName, c.latitude, c.longitude, c.color, c.labelAngle, true);
    }

    void AddEntry(string craterName, float lat, float lon, Color color, float angle, bool makeDot)
    {
        float r = globe.globeRadius;

        GameObject root = new GameObject(craterName + "Mark");
        root.transform.SetParent(pivot, false);
        root.transform.localPosition = LatLonToLocal(lat, lon, r * 1.005f);

        if (makeDot)
        {
            GameObject d = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            d.name = craterName + "Marker";
            Destroy(d.GetComponent<Collider>());
            d.transform.SetParent(root.transform, false);
            d.transform.localScale = Vector3.one * (r * markerSizeFraction);

            Material m = new Material(sphereRenderer.sharedMaterial);
            m.mainTexture = null;
            if (m.HasProperty("_BaseMap")) m.SetTexture("_BaseMap", null);
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", color);
            m.color = color;
            d.GetComponent<MeshRenderer>().sharedMaterial = m;
        }

        GameObject lg = new GameObject(craterName + "Label");
        lg.transform.SetParent(root.transform, false);
        TextMeshPro tmp = lg.AddComponent<TextMeshPro>();
        tmp.text = craterName;
        tmp.fontSize = 36f;
        tmp.alignment = TextAlignmentOptions.Center;
        tmp.color = labelColor;
        lg.transform.localScale = Vector3.one * (r * labelSizeFraction / 3.6f);

        GameObject ln = new GameObject(craterName + "Line");
        ln.transform.SetParent(root.transform, false);
        LineRenderer lr = ln.AddComponent<LineRenderer>();
        lr.useWorldSpace = true;
        lr.positionCount = 2;
        lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        Material lm = new Material(sphereRenderer.sharedMaterial);
        lm.mainTexture = null;
        if (lm.HasProperty("_BaseMap")) lm.SetTexture("_BaseMap", null);
        if (lm.HasProperty("_BaseColor")) lm.SetColor("_BaseColor", labelColor);
        lm.color = labelColor;
        lr.sharedMaterial = lm;

        entries.Add(new Entry { root = root.transform, label = lg.transform, line = lr, angle = angle });
    }

    // Same convention as MoonGlobe: lon 0 faces +Z.
    static Vector3 LatLonToLocal(float latDeg, float lonDeg, float r)
    {
        float la = latDeg * Mathf.Deg2Rad;
        float lo = lonDeg * Mathf.Deg2Rad;
        return new Vector3(-Mathf.Cos(la) * Mathf.Sin(lo), Mathf.Sin(la), Mathf.Cos(la) * Mathf.Cos(lo)) * r;
    }
}