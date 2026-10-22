using UnityEngine;

public class PinchZoom : MonoBehaviour
{
    public string runtimeTargetName = "FaustiniTerrain";
    public Transform target;

    [Header("Limits (multiplier of the starting scale)")]
    public float minScale = 0.2f;
    public float maxScale = 6f;

    [Header("Speed")]
    public float mouseWheelSpeed = 0.1f;
    public float buttonStep = 1.25f;

    float lastPinchDistance;
    Transform baseFor;
    Vector3 baseScale = Vector3.one;

    bool EnsureTarget()
    {
        if (target != null) return true;
        GameObject go = GameObject.Find(runtimeTargetName);
        if (go != null) target = go.transform;
        return target != null;
    }

    void CaptureBase()
    {
        if (baseFor != target)
        {
            baseFor = target;
            baseScale = target.localScale;
        }
    }

    void Update()
    {
        if (!EnsureTarget()) return;

        if (Input.touchCount == 2)
        {
            Touch a = Input.GetTouch(0);
            Touch b = Input.GetTouch(1);
            float dist = Vector2.Distance(a.position, b.position);

            if (a.phase == TouchPhase.Began || b.phase == TouchPhase.Began)
            {
                lastPinchDistance = dist;
                return;
            }

            if (lastPinchDistance > 1f)
                ApplyFactor(dist / lastPinchDistance);

            lastPinchDistance = dist;
        }
        else
        {
            lastPinchDistance = 0f;
            float wheel = Input.mouseScrollDelta.y;
            if (Mathf.Abs(wheel) > 0.001f)
                ApplyFactor(1f + wheel * mouseWheelSpeed);
        }
    }

    void ApplyFactor(float factor)
    {
        if (!EnsureTarget()) return;
        CaptureBase();
        float current = target.localScale.x / Mathf.Max(baseScale.x, 0.0001f);
        float next = Mathf.Clamp(current * factor, minScale, maxScale);
        target.localScale = baseScale * next;
    }

    public void ZoomIn()    { ApplyFactor(buttonStep); }
    public void ZoomOut()   { ApplyFactor(1f / buttonStep); }
    public void ResetZoom() { if (EnsureTarget()) { CaptureBase(); target.localScale = baseScale; } }
}