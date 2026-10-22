using UnityEngine;
using Vuforia;

public class ARPlacement : MonoBehaviour
{
    public TerrainGenerator terrainGenerator;
    private bool terrainPlaced = false;

    void OnEnable()
    {
        var observerHandler = GetComponent<DefaultObserverEventHandler>();
        if (observerHandler != null)
        {
            observerHandler.OnTargetFound.AddListener(HandleTargetFound);
        }
    }

    void OnDisable()
    {
        var observerHandler = GetComponent<DefaultObserverEventHandler>();
        if (observerHandler != null)
        {
            observerHandler.OnTargetFound.RemoveListener(HandleTargetFound);
        }
    }

    void HandleTargetFound()
    {
        if (terrainPlaced) return;

        GameObject terrain = terrainGenerator.GenerateTerrain();
        terrain.transform.position = transform.position;
        terrain.transform.rotation = transform.rotation;
        terrain.transform.localScale = Vector3.one * 0.05f;

        terrainPlaced = true;
    }
}