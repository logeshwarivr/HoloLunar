using UnityEngine;
using Vuforia;

// AR SCENE ONLY. Put this on the Vuforia Image Target object.
// It reads the size of the printed target, builds the terrain mesh at that
// size, and attaches it to the target.
public class TerrainOnTarget : MonoBehaviour
{
    public TerrainGenerator generator;

    [Tooltip("Terrain height as a fraction of the target width.")]
    [Range(0.02f, 0.5f)]
    public float heightRatio = 0.15f;

    void Start()
    {
        if (generator == null)
        {
            Debug.LogError("TerrainOnTarget: drag your Terrain Generator object into the Generator slot.");
            return;
        }

        generator.buildAsMesh = true;   // Terrain can't rotate/scale, mesh can

        // Match the terrain to the size of the Image Target
        ImageTargetBehaviour target = GetComponent<ImageTargetBehaviour>();
        if (target != null)
        {
            Vector2 size = target.GetSize();
            Debug.Log("TerrainOnTarget: Image Target size = " + size.x + " x " + size.y);

            if (size.x > 0f && size.y > 0f)
            {
                generator.terrainWidth = size.x;
                generator.terrainLength = size.y;
                generator.terrainHeight = size.x * heightRatio;
            }
        }

        GameObject t = generator.GenerateTerrain();
        t.transform.SetParent(transform, false);
        t.transform.localPosition = Vector3.zero;
        t.transform.localRotation = Quaternion.identity;
        t.transform.localScale = Vector3.one;

        // Hidden until the target is seen (Vuforia's Default Observer Event
        // Handler switches renderers on and off for children of the target).
        Renderer r = t.GetComponent<Renderer>();
        if (r != null) r.enabled = false;
    }
}