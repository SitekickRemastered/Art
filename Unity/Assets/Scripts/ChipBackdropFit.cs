using UnityEngine;

namespace Sitekick
{
	/// <summary>
	/// Makes a background chip's backdrop cover the camera whatever the window
	/// shape is. The prefab is authored for the gallery's reference view; when
	/// the real view is wider or taller the backdrop grows (never shrinks) and
	/// re-centres on the camera, so the frame is never left half empty.
	/// </summary>
	[DisallowMultipleComponent]
	public class ChipBackdropFit : MonoBehaviour
	{
		/// <summary>The view the prefab's placement was authored for.</summary>
		public Vector2 referenceView = new Vector2( 14.667f, 11f );

		protected Camera cam;

		protected void OnEnable()
		{
			cam = Camera.main;
		}

		// LateUpdate, not OnEnable: the gallery sets the instance's local scale
		// right after instantiating, which would undo a scale applied there, and
		// the game view can be resized at any time.
		protected void LateUpdate()
		{
			Apply();
		}

		/// <summary>Fit to the camera now; the editor uses this outside play mode.</summary>
		public void Apply()
		{
			if ( cam == null )
				cam = Camera.main;
			if ( cam == null )
				return;

			float height = cam.orthographicSize * 2f;
			float width = height * cam.aspect;
			float scale = Mathf.Max( 1f, width / referenceView.x, height / referenceView.y );
			transform.localScale = Vector3.one * scale;

			var centre = cam.transform.position;
			var position = transform.position;
			transform.position = new Vector3( centre.x, centre.y, position.z );
		}
	}
}
