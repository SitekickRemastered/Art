using UnityEngine;

namespace Sitekick
{
	/// <summary>
	/// Plays a sprite-swap movie at a fixed frame rate. The weekday chips (1-6)
	/// are a 51-frame boot screen at 12 fps in Flash, and every frame is a whole
	/// 375x300 stage drawing, so swapping the renderer's sprite reproduces the
	/// timeline without an Animator or a clip per frame.
	/// </summary>
	public class ChipBackdropPlayer : MonoBehaviour
	{
		public SpriteRenderer target;
		public Sprite[] frames;
		public float fps = 12f;

		protected float elapsed;
		protected int shown = -1;

		protected void OnEnable()
		{
			elapsed = 0f;
			shown = -1;
			Apply();
		}

		protected void Update()
		{
			if ( frames == null || frames.Length == 0 || fps <= 0f )
				return;

			elapsed += Time.deltaTime;
			var next = Mathf.FloorToInt( elapsed * fps ) % frames.Length;
			if ( next != shown )
			{
				shown = next;
				Apply();
			}
		}

		protected void Apply()
		{
			if ( target == null || frames == null || frames.Length == 0 )
				return;

			shown = Mathf.Clamp( shown < 0 ? 0 : shown, 0, frames.Length - 1 );
			target.sprite = frames[ shown ];
		}
	}
}
