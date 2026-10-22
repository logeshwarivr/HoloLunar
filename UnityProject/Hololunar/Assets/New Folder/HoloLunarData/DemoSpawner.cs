using UnityEngine;

public class DemoSpawner : MonoBehaviour
{
    public TerrainGenerator terrainGenerator;

    void Start()
    {
        GameObject terrain = terrainGenerator.GenerateTerrain();
        terrain.transform.position = Vector3.zero;
    }
}