using UnityEngine;

// DESKTOP PREVIEW ONLY. Put this on the Main Camera in DemoScene.
// Do NOT use it in the AR scene: Vuforia controls the camera there.
public class FrameTerrain : MonoBehaviour
{
    public float distanceFactor = 0.7f;   // how far back (x terrain size)
    public float heightFactor = 0.4f;     // how high up (x terrain size)

    GameObject target;

    void LateUpdate()
    {
        if (target == null)
        {
            target = GameObject.Find("FaustiniTerrain");
            if (target == null) return;
        }

        Bounds b = GetBounds(target);
        float size = Mathf.Max(b.size.x, b.size.z);
        transform.position = b.center + new Vector3(0, size * heightFactor, -size * distanceFactor);
        transform.LookAt(b.center);
    }

    Bounds GetBounds(GameObject g)
    {
        Terrain t = g.GetComponent<Terrain>();
        if (t != null)
            return new Bounds(t.transform.position + t.terrainData.size * 0.5f, t.terrainData.size);

        Renderer r = g.GetComponentInChildren<Renderer>();
        return r != null ? r.bounds : new Bounds(g.transform.position, Vector3.one);
    }
}